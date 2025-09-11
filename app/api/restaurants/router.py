from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time, timezone
from app.database.db import get_db
from app.api.cities.models import City
from typing import List, Optional, Dict, Any
from app.utils.embeddings import get_embedding
import subprocess
from sqlalchemy import text, func, Table, MetaData, create_engine
import json, math, httpx, subprocess
from app.api.restaurants.schema import RestaurantCreate, RestaurantRead, RestaurantUpdate, RestaurantDelete
from app.api.restaurants.models import Restaurants
import os
from app.utils.helper import CommonResponse
from app.utils.searching import apply_searching
from app.utils.sorting import apply_sorting
from app.utils.pagination import get_pagination_metadata
from sqlalchemy.exc import SQLAlchemyError
from app.utils.helper import safe_db_operation

router = APIRouter(prefix="/restaurant", tags=["Restaurants"])

def generate_restaurant_id(db: Session) -> str:
    last_place = db.query(Restaurants).order_by(Restaurants.id.desc()).first()
    if not last_place or not last_place.restaurant_id:
        return "restaurant_00001"
    last_num = int(last_place.restaurant_id.split("_")[1])
    return f"restaurant_{last_num+1:05d}"



@router.post("/create")
@safe_db_operation("CreateRestaurant")
def create_restaurant(restaurant_req: RestaurantCreate, db: Session = Depends(get_db)):
    """
    Accept JSON, ignore provided id, auto-generate country_id,
    prevent duplicate entries, and store embeddings.
    """


    # --- Duplicate check ---
    existing_restaurant = (
        db.query(Restaurants)
        .filter(
            Restaurants.name.ilike(restaurant_req.name), Restaurants.city_id == restaurant_req.city_id)
        .first()
    )
    if existing_restaurant:
        # return {"message": "Restaurant already exists", "is_success": False}
        return CommonResponse(
            is_success=False,
            message="Restaurant already exists",
            status_code=201
        )

    # --- Generate new restaurant_id ---
    restaurant_id = generate_restaurant_id(db)

    # --- Prepare data ---
    data = restaurant_req.model_dump()  # ignore incoming id
    data["restaurant_id"] = restaurant_id
    # data["last_verified"] = data.get("last_verified", datetime.now(timezone.utc).date())

    restaurant = Restaurants(**data)
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    # return {"message": "Restaurant data inserted successfully", "is_success": True}
    return CommonResponse(
            is_success=True,
            message="Restaurant data inserted successfully",
            status_code=201
        )


@router.get("/get_all_restaurants", response_model=CommonResponse[List[RestaurantRead]])
@safe_db_operation("GetAllRestaurants")
def get_all_restaurants(
    is_active: Optional[bool] = Query(None, description="Filter by active (true)/inactive (false) status"),
    country_id: Optional[str] = Query(None, description="Filter by country_id"),
    state_id: Optional[str] = Query(None, description="Filter by state_id"),
    city_id: Optional[int] = Query(None, description="Filter by city_id"),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
    ):

    base_query = db.query(Restaurants)

    if is_active is not None:
        base_query = base_query.filter(Restaurants.is_active == bool(is_active))

    if country_id:
        base_query = base_query.filter(Restaurants.country_id == country_id)

        if state_id:
            base_query = base_query.filter(Restaurants.state_id == state_id)

            if city_id:
                base_query = base_query.filter(Restaurants.city_id == city_id)
    # Apply search
    base_query = apply_searching(base_query, Restaurants, ["name"], search)

    total_count = base_query.count()

    # Apply sorting
    base_query = apply_sorting(base_query, Restaurants, sort_by, sort_order)
    total_count = base_query.count()
    

    # Apply pagination if both page and page_size provided
    if page and page_size:
        skip = (page - 1) * page_size
        base_query = base_query.offset(skip).limit(page_size)
        pagination = get_pagination_metadata(total_count, skip, page_size)
    else:
        pagination = None

    restaurants = base_query.all()

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Restaurants fetched successfully",
        is_success=True,
        result=restaurants,
        pagination=pagination
    )

@router.get("/get_restaurant/{restaurant_id}", response_model=CommonResponse[RestaurantRead])
@safe_db_operation("GetRestaurant")
def get_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db)
    ):

    base_query = db.query(Restaurants).filter(Restaurants.id == restaurant_id)
    restaurant = base_query.first()

    if not restaurant:
        return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="No restaurant found",
        is_success=False,
        result=restaurant
    )

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Restaurant fetched successfully",
        is_success=True,
        result=restaurant
    )

@router.put("/update_restaurant", response_model=CommonResponse[RestaurantUpdate])
@safe_db_operation("UpdateRestaurant")
def update_restaurant(update: RestaurantUpdate,
                       db: Session = Depends(get_db)):
    # 1. First check if user exists
    restaurant = db.query(Restaurants).filter(Restaurants.id == update.id).first()
    if not restaurant:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="Restaurant not found",
            is_success=False,
            result=None,
        )

    # 2. Check if restaurant exists
    existing_restaurant = db.query(Restaurants).filter(
        Restaurants.name == update.name,
        Restaurants.id != update.id
    ).first()
    if existing_restaurant:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="Restaurant with this name already exists.",
            is_success=False,
            result=None
        )


    update_data = update.dict(exclude={'id'})

    restaurant.update(db, **update_data)

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Restaurant updated successfully",
        is_success=True,
        result=None
    )


@router.patch("/delete_restaurant", response_model=CommonResponse,
               status_code=status.HTTP_200_OK)
@safe_db_operation("DeleteRestaurant")
def delete_restaurant(update: RestaurantDelete, db: Session = Depends(get_db)):

    restaurant = db.query(Restaurants).filter(Restaurants.id == update.id).first()
    if not restaurant:
        return CommonResponse.response_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Restaurant not found",
            result=None,
            is_success=False
        )

    restaurant.update(db, is_active=update.is_active)

    if update.is_active:
        message = "Restaurant restored successfully"
    else:
        message = "Restaurant deleted successfully"

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message=message,
        is_success=True,
        result=None
    )