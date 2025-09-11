from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time, timezone
from app.database.db import get_db
from app.api.cities.models import City
from app.api.states.models import State
from app.api.countries.models import Country
from typing import List, Optional, Dict, Any
from app.utils.embeddings import get_embedding
import subprocess
from sqlalchemy import text, func, Table, MetaData, create_engine
import json, math, httpx, subprocess
from app.api.cities.schema import CityCreate, CityRead, CityUpdate, CityDelete
import os
from app.utils.helper import CommonResponse
from app.utils.searching import apply_searching
from app.utils.sorting import apply_sorting
from app.utils.pagination import get_pagination_metadata
from sqlalchemy.exc import SQLAlchemyError
from app.utils.helper import safe_db_operation

router = APIRouter(prefix="/city", tags=["Cities"])

def generate_city_id(db: Session) -> str:
    last_place = db.query(City).order_by(City.id.desc()).first()
    if not last_place or not last_place.city_id:
        return "city_00001"
    last_num = int(last_place.city_id.split("_")[1])
    return f"city_{last_num+1:05d}"



@router.post("/create")
@safe_db_operation("CreateCity")
def create_city(city_req: CityCreate, db: Session = Depends(get_db)):
    """
    Accept JSON, ignore provided id, auto-generate country_id,
    prevent duplicate entries, and store embeddings.
    """


    # --- Duplicate check ---
    existing_city = (
        db.query(City)
        .filter(
            City.name.ilike(city_req.name), City.state_id == city_req.state_id, City.country_id == city_req.country_id
        )
        .first()
    )
    if existing_city:
        # return {"message": "City already exists", "is_success": False}
        return CommonResponse(
            is_success=False,
            message="City already exists",
            status_code=201
        )

    # --- Generate new city_id ---
    city_id = generate_city_id(db)

    # --- Prepare data ---
    data = city_req.model_dump()  # ignore incoming id
    data["city_id"] = city_id
    # data["last_verified"] = data.get("last_verified", datetime.now(timezone.utc).date())

    city = City(**data)
    db.add(city)
    db.commit()
    db.refresh(city)

    # return {"message": "City data inserted successfully", "is_success": True}
    return CommonResponse(
            is_success=True,
            message="City data inserted successfully",
            status_code=201
        )


@router.get("/get_all_cities", response_model=CommonResponse[List[CityRead]])
@safe_db_operation("GetAllCities")
def get_all_cities(
    is_active: Optional[bool] = Query(None, description="Filter by active (true)/inactive (false) status"),
    state_id: Optional[str] = Query(None, description="Filter by state_id"),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
    ):

    base_query = db.query(City)

    if is_active is not None:
        base_query = base_query.filter(City.is_active == bool(is_active))

    if state_id:
        base_query = base_query.filter(City.state_id == state_id)

    # Apply search
    base_query = apply_searching(base_query, City, ["name"], search)

    total_count = base_query.count()

    # Apply sorting
    base_query = apply_sorting(base_query, City, sort_by, sort_order)
    total_count = base_query.count()
    

    # Apply pagination if both page and page_size provided
    if page and page_size:
        skip = (page - 1) * page_size
        base_query = base_query.offset(skip).limit(page_size)
        pagination = get_pagination_metadata(total_count, skip, page_size)
    else:
        pagination = None

    cities = base_query.all()

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Cities fetched successfully",
        is_success=True,
        result=cities,
        pagination=pagination
    )

@router.get("/get_city/{city_id}", response_model=CommonResponse[CityRead])
@safe_db_operation("GetCity")
def get_city(
    city_id: int,
    db: Session = Depends(get_db)
    ):

    base_query = db.query(City).filter(City.id == city_id)
    city = base_query.first()

    if not city:
        return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="No city found",
        is_success=False,
        result=city
    )

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="City fetched successfully",
        is_success=True,
        result=city
    )

@router.put("/update_city", response_model=CommonResponse[CityUpdate])
@safe_db_operation("UpdateCity")
def update_city(update: CityUpdate,
                 db: Session = Depends(get_db)):
    # 1. First check if user exists
    city = db.query(City).filter(City.id == update.id).first()
    if not city:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="City not found",
            is_success=False,
            result=None,
        )

    # 2. Check if course exists
    existing_city = db.query(City).filter(
        City.name == update.name,
        City.id != update.id
    ).first()
    if existing_city:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="City with this name already exists.",
            is_success=False,
            result=None
        )


    update_data = update.dict(exclude={'id'})

    city.update(db, **update_data)

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="City updated successfully",
        is_success=True,
        result=None
    )


@router.patch("/delete_city", response_model=CommonResponse,
               status_code=status.HTTP_200_OK)
@safe_db_operation("DeleteCity")
def delete_city(update: CityDelete, db: Session = Depends(get_db)):

    city = db.query(City).filter(City.id == update.id).first()
    if not city:
        return CommonResponse.response_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            message="City not found",
            result=None,
            is_success=False
        )

    city.update(db, is_active=update.is_active)

    if update.is_active:
        message = "City restored successfully"
    else:
        message = "City deleted successfully"

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message=message,
        is_success=True,
        result=None
    )