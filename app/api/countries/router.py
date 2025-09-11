from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time, timezone
from app.database.db import get_db
from app.api.countries.models import Country
from typing import List, Optional, Dict, Any
from app.utils.embeddings import get_embedding
import subprocess
from sqlalchemy import text, func, Table, MetaData, create_engine
import json, math, httpx, subprocess
from app.api.countries.schema import CountryCreate, CountryRead, CountryUpdate, CountryDelete
import os
from app.utils.helper import CommonResponse
from app.utils.searching import apply_searching
from app.utils.sorting import apply_sorting
from app.utils.pagination import get_pagination_metadata
from sqlalchemy.exc import SQLAlchemyError
from app.utils.helper import safe_db_operation

router = APIRouter(prefix="/country", tags=["Country"])

def generate_country_id(db: Session) -> str:
    last_place = db.query(Country).order_by(Country.id.desc()).first()
    if not last_place or not last_place.country_id:
        return "country_00001"
    last_num = int(last_place.country_id.split("_")[1])
    return f"country_{last_num+1:05d}"



@router.post("/create")
@safe_db_operation("CreateCountry")
def create_country(country_req: CountryCreate, db: Session = Depends(get_db)):
    """
    Accept JSON, ignore provided id, auto-generate country_id,
    prevent duplicate entries, and store embeddings.
    """


    # --- Duplicate check ---
    existing_country = (
        db.query(Country)
        .filter(
            Country.name.ilike(country_req.name)
        )
        .first()
    )
    if existing_country:
        # return {"message": "State already exists", "is_success": False}
        return CommonResponse(
            is_success=False,
            message="Country already exists",
            status_code=201
        )

    # --- Generate new place_id ---
    country_id = generate_country_id(db)

    # --- Prepare data ---
    data = country_req.model_dump()  # ignore incoming id
    data["country_id"] = country_id
    # data["last_verified"] = data.get("last_verified", datetime.now(timezone.utc).date())

    country = Country(**data)
    db.add(country)
    db.commit()
    db.refresh(country)
    
    # return {"message": "State data inserted successfully", "is_success": True}
    return CommonResponse(
            is_success=True,
            message="Country data inserted successfully",
            status_code=201
        )


@router.get("/get_all_countries", response_model=CommonResponse[List[CountryRead]])
@safe_db_operation("GetAllCountries")
def get_all_countries(
    is_active: Optional[bool] = Query(None, description="Filter by active (true)/inactive (false) status"),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
    ):

    base_query = db.query(Country)

    if is_active is not None:
        base_query = base_query.filter(Country.is_active == bool(is_active))

    # Apply search
    base_query = apply_searching(base_query, Country, ["name"], search)

    total_count = base_query.count()

    # Apply sorting
    base_query = apply_sorting(base_query, Country, sort_by, sort_order)
    total_count = base_query.count()
    

    # Apply pagination if both page and page_size provided
    if page and page_size:
        skip = (page - 1) * page_size
        base_query = base_query.offset(skip).limit(page_size)
        pagination = get_pagination_metadata(total_count, skip, page_size)
    else:
        pagination = None

    countries = base_query.all()


    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Countries fetched successfully",
        is_success=True,
        result=countries,
        pagination=pagination
    )

@router.get("/get_country/{country_id}", response_model=CommonResponse[CountryRead])
@safe_db_operation("GetCountry")
def get_country(
    country_id : int,
    db: Session = Depends(get_db)
    ):

    base_query = db.query(Country).filter(Country.id == country_id)
    country = base_query.first()

    if not country:
        return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="No country found",
        is_success=False,
        result=country
    )

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Country fetched successfully",
        is_success=True,
        result=country
    )

@router.put("/update_country", response_model=CommonResponse[CountryRead])
@safe_db_operation("UpdateCountry")
def update_country(update: CountryUpdate,
                  db: Session = Depends(get_db)):
    # 1. First check if user exists
    country_update = db.query(Country).filter(Country.id == update.id).first()
    if not country_update:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="Country not found",
            is_success=False,
            result=None,
        )

    # 2. Check if course exists
    existing_country = db.query(Country).filter(
        Country.name == update.name, 
        Country.id != update.id
        ).first()
    if existing_country:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="Country with this name already exists.",
            is_success=False,
            result=None
        )


    update_data = update.dict(exclude={'id'})

    country_update.update(db, **update_data)

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Country updated successfully",
        is_success=True,
        result=None
    )

    
@router.patch("/delete_country", response_model=CommonResponse,
               status_code=status.HTTP_200_OK)
@safe_db_operation("DeleteCountry")
def delete_country(update: CountryDelete, db: Session = Depends(get_db)):

    country = db.query(Country).filter(Country.id == update.id).first()
    if not country:
        return CommonResponse.response_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Country not found",
            result=None,
            is_success=False
        )

    country.update(db,is_active = update.is_active)

    if update.is_active:
        message = "Country restored successfully"
    else:
        message = "Country deleted successfully"

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message=message,
        is_success=True,
        result=None
    )