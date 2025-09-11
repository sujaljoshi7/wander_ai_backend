from app.api.cities.router import generate_city_id
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time, timezone
from app.database.db import get_db
from app.api.places.models import Places
from typing import List, Optional, Dict, Any
from app.utils.embeddings import get_embedding
import subprocess
from sqlalchemy import text, func, Table, MetaData, create_engine
import json, math, httpx, subprocess
from app.api.places.schema import PlaceCreate, PlaceRead, PlaceUpdate, PlaceDelete
from app.utils.helper import CommonResponse, safe_db_operation, format_best_time_of_day
from app.utils.searching import apply_searching
from app.utils.sorting import apply_sorting
from app.utils.pagination import get_pagination_metadata

import os

router = APIRouter(prefix="/places", tags=["Places"])

# EARTH_KM = 6371.0



def generate_place_id(db: Session) -> str:
    last_place = db.query(Places).order_by(Places.id.desc()).first()
    if not last_place or not last_place.place_id:
        return "place_00001"
    last_num = int(last_place.place_id.split("_")[1])
    return f"place_{last_num+1:05d}"

# def generate_embedding(text: str):
#     model = EmbeddingModel()  # Initialize your model
#     embedding = model.encode(text)  # Convert text to embedding
#     return embedding

def create_embedding_text_from_data(data):
    """
    Create comprehensive text for embedding generation using multiple fields
    """
    embedding_parts = []
    
    # Core identity
    if data.get('name'):
        embedding_parts.append(f"Place: {data['name']}")
    
    if data.get('city') and data.get('state') and data.get('country'):
        embedding_parts.append(f"Location: {data['city']}, {data['state']}, {data['country']}")
    
    if data.get('type'):
        embedding_parts.append(f"Type: {data['type']}")
    
    # Description and context
    if data.get('description'):
        embedding_parts.append(f"Description: {data['description']}")
    
    # What it's famous for
    if data.get('famous_for'):
        famous_for_list = data['famous_for'] if isinstance(data['famous_for'], list) else [data['famous_for']]
        embedding_parts.append(f"Famous for: {', '.join(famous_for_list)}")
    
    # Tags and characteristics
    if data.get('tags'):
        tags_list = data['tags'] if isinstance(data['tags'], list) else [data['tags']]
        embedding_parts.append(f"Features: {', '.join(tags_list)}")
    
    # Suitability
    if data.get('suitable_for'):
        suitable_list = data['suitable_for'] if isinstance(data['suitable_for'], list) else [data['suitable_for']]
        embedding_parts.append(f"Suitable for: {', '.join(suitable_list)}")
    
    # Temporal information
    if data.get('best_months'):
        months_list = data['best_months'] if isinstance(data['best_months'], list) else [data['best_months']]
        embedding_parts.append(f"Best months to visit: {', '.join(months_list)}")
    
    if 'best_time_of_day_to_visit' in data:
        formatted_times = format_best_time_of_day(data['best_time_of_day_to_visit'])
        embedding_parts.append("Best time of day: " + ", ".join(formatted_times))

    # Duration and rating
    if data.get('avg_visit_mins'):
        embedding_parts.append(f"Average visit duration: {data['avg_visit_mins']} minutes")
    
    if data.get('rating'):
        embedding_parts.append(f"Rating: {data['rating']}/5.0")
    
    # Additional notes
    if data.get('notes'):
        embedding_parts.append(f"Notes: {data['notes']}")
    
    return " | ".join(embedding_parts) if embedding_parts else None

def generate_embedding(text: str) -> Optional[List[float]]:
    """Temporary fallback - returns None for now"""
    if not text:
        return None
    
    # Simple fallback - creates a dummy 384-dimensional embedding
    import hashlib
    import numpy as np
    
    try:
        hash_object = hashlib.sha256(text.encode())
        hash_bytes = hash_object.digest()
        np.random.seed(int.from_bytes(hash_bytes[:4], byteorder='big'))
        embedding = np.random.normal(0, 1, 384)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()
    except:
        return None


@router.post("/create")
@safe_db_operation("CreatePlace") 
def create_place(place_req: PlaceCreate, db: Session = Depends(get_db)):
    # Check duplicate by name, state_id, country_id - assuming those IDs are provided or resolved elsewhere
    existing_place = (
        db.query(Places)
        .filter(
            Places.name.ilike(place_req.name),
            Places.state == place_req.state,
            Places.country == place_req.country
        )
        .first()
    )
    if existing_place:
        return CommonResponse(
            is_success=False,
            message="Place already exists",
            result=None,
            status_code=409
        )


    # Auto-generate a unique place_id
    place_id = generate_place_id(db)

    # Prepare dict for SQLAlchemy model
    data = place_req.model_dump()

    data["place_id"] = place_id
    data["last_verified"] = data.get("last_verified", datetime.now(timezone.utc).date())

    # Flatten avg_cost_per_person to float amount if present
    if data.get("avg_cost_per_person") and isinstance(data["avg_cost_per_person"], dict):
        data["avg_cost_per_person"] = data["avg_cost_per_person"].get("amount")

    # Create embedding text from place data
    embedding_text = create_embedding_text_from_data(data)  # implement this helper function as explained previously

    # Generate embeddings if text present
    if embedding_text:
        embedding = generate_embedding(embedding_text)  # your embedding function returning a list of floats
        if embedding:
            data["embedding"] = embedding

    # Create Places SQLAlchemy model instance
    place = Places(**data)
    db.add(place)
    db.commit()
    db.refresh(place)

    return CommonResponse(
        is_success=True,
        message="Place data inserted successfully",
        result=data,
        status_code=201
    )

@router.get("/get_all_places", response_model=CommonResponse[List[PlaceRead]])
@safe_db_operation("GetAllPlaces")
def get_all_places(
    is_active: Optional[bool] = Query(None, description="Filter by active (true)/inactive (false) status"),
    state_id: Optional[str] = Query(None, description="Filter by state_id"),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
    ):

    base_query = db.query(Places)

    if is_active is not None:
        base_query = base_query.filter(Places.is_active == bool(is_active))

    if state_id:
        base_query = base_query.filter(Places.state_id == state_id)

    # Apply search
    base_query = apply_searching(base_query, Places, ["name"], search)

    total_count = base_query.count()

    # Apply sorting
    base_query = apply_sorting(base_query, Places, sort_by, sort_order)
    total_count = base_query.count()
    

    # Apply pagination if both page and page_size provided
    if page and page_size:
        skip = (page - 1) * page_size
        base_query = base_query.offset(skip).limit(page_size)
        pagination = get_pagination_metadata(total_count, skip, page_size)
    else:
        pagination = None

    places = base_query.all()

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Places fetched successfully",
        is_success=True,
        result=places,
        pagination=pagination
    )

@router.get("/get_place/{place_id}", response_model=CommonResponse[PlaceRead])
@safe_db_operation("GetPlace")
def get_place(
    place_id: int,
    db: Session = Depends(get_db)
    ):

    base_query = db.query(Places).filter(Places.id == place_id)
    place = base_query.first()

    if not place:
        return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="No place found",
        is_success=False,
        result=place
    )

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Place fetched successfully",
        is_success=True,
        result=place
    )

@router.put("/update_place", response_model=CommonResponse[PlaceUpdate])
@safe_db_operation("UpdatePlace")
def update_place(update: PlaceUpdate,
                 db: Session = Depends(get_db)):
    # 1. First check if user exists
    place = db.query(Places).filter(Places.id == update.id).first()
    if not place:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="Place not found",
            is_success=False,
            result=None,
        )

    # 2. Check if place exists
    existing_place = db.query(Places).filter(
        Places.name == update.name,
        Places.id != update.id
    ).first()
    if existing_place:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="Place with this name already exists.",
            is_success=False,
            result=None
        )


    update_data = update.dict(exclude={'id'})

    place.update(db, **update_data)

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="Place updated successfully",
        is_success=True,
        result=None
    )


@router.patch("/delete_place", response_model=CommonResponse,
               status_code=status.HTTP_200_OK)
@safe_db_operation("DeletePlace")
def delete_place(update: PlaceDelete, db: Session = Depends(get_db)):

    place = db.query(Places).filter(Places.id == update.id).first()
    if not place:
        return CommonResponse.response_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Place not found",
            result=None,
            is_success=False
        )

    place.update(db, is_active=update.is_active)

    if update.is_active:
        message = "Place restored successfully"
    else:
        message = "Place deleted successfully"

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message=message,
        is_success=True,
        result=None
    )




















# @router.post("/create")
# def create_place(place_req: dict, db: Session = Depends(get_db)):
#     """
#     Accept JSON, ignore provided id, auto-generate place_id,
#     prevent duplicate entries, and store embeddings.
#     """

#     # --- Required defaults ---
#     for f in ["name", "city", "state", "country"]:
#         if f not in place_req or not str(place_req[f]).strip():
#             raise HTTPException(status_code=400, detail=f"Missing required field: {f}")

#     name = place_req["name"].strip()
#     city = place_req["city"].strip()
#     state = place_req["state"].strip()
#     country = place_req["country"].strip()

#     # --- Duplicate check ---
#     existing_place = (
#         db.query(Places)
#         .filter(
#             Places.name.ilike(name),
#             Places.city.ilike(city),
#             Places.state.ilike(state),
#             Places.country.ilike(country),
#         )
#         .first()
#     )
#     if existing_place:
#         return {"message": "Entry already exists", "place_id": existing_place.place_id}

#     # --- Generate new place_id ---
#     place_id = generate_place_id(db)

#     # --- Filter valid DB columns ---
#     valid_columns = {c.name for c in Places.__table__.columns}
#     filtered_data = {}
#     extras = {}

#     for key, value in place_req.items():
#         if key == "id":  # ignore incoming id
#             continue
#         if key in valid_columns:
#             filtered_data[key] = value
#         else:
#             extras[key] = value

#     # --- Add system-generated fields ---
#     filtered_data["place_id"] = place_id
#     filtered_data["extras"] = extras
#     if "last_verified" not in filtered_data:
#         filtered_data["last_verified"] = datetime.now().date()

#     # --- Generate embedding ---
#     embedding_text = " ".join([
#         filtered_data.get("name", ""),
#         filtered_data.get("city", ""),
#         filtered_data.get("state", ""),
#         filtered_data.get("country", ""),
#         filtered_data.get("description", "")
#     ])
#     filtered_data["embedding"] = get_embedding(embedding_text)

#     # --- Save to DB ---
#     place_obj = Places(**filtered_data)
#     db.add(place_obj)
#     db.commit()
#     db.refresh(place_obj)

#     return {"message": "Place data inserted successfully", "place_id": place_id}



# WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# @router.post("/create1", status_code=status.HTTP_201_CREATED)
# def create_place(place_req: PlaceCreate, db: Session = Depends(get_db)):
#     """
#     Accept JSON, ignore provided id, auto-generate place_id,
#     prevent duplicate entries, and store embeddings.
#     """

#     # Deduplication check
#     name = place_req.name.strip()
#     city = place_req.city.strip()
#     state = place_req.state.strip()
#     country = place_req.country.strip()

#     existing_place = (
#         db.query(Places)
#         .filter(
#             func.lower(func.trim(Places.name)) == func.lower(name),
#             func.lower(func.trim(Places.city)) == func.lower(city),
#             func.lower(func.trim(Places.state)) == func.lower(state),
#             func.lower(func.trim(Places.country)) == func.lower(country),
#         )
#         .first()
#     )
#     if existing_place:
#         return {
#             "message": "Entry already exists",
#             "place_id": existing_place.place_id
#         }

#     # Generate new place_id
#     place_id = generate_place_id(db)

#     # Convert Pydantic model → dict
#     src: Dict[str, Any] = place_req.dict(exclude_unset=False)

#     # Extract valid DB columns
#     valid_columns = {c.name for c in Places.__table__.columns}
#     filtered_data: Dict[str, Any] = {}
#     extras: Dict[str, Any] = {}

#     def ensure_list(val):
#         return val if isinstance(val, list) else []

#     # Separate known vs unknown keys
#     for key, value in src.items():
#         if key in ["id", "place_id"]:
#             continue
#         if key in valid_columns:
#             filtered_data[key] = value
#         else:
#             extras[key] = value
# # Merge: if request already had "extras", combine it with new extras
#     req_extras = src.get("extras", {})
#     if req_extras and isinstance(req_extras, dict):
#         extras.update(req_extras)
#     # Defaults
#     filtered_data.setdefault("avg_visit_mins", 60)
#     # Save into filtered_data
#     filtered_data["extras"] = extras

#     # Open hours
#     if place_req.open_hours:
#         filtered_data["open_hours"] = dict(place_req.open_hours.dict())
#     else:
#         filtered_data["open_hours"] = {d: [] for d in WEEKDAYS}

#     # Arrays
#     filtered_data["tags"] = ensure_list(filtered_data.get("tags") or [])
#     filtered_data["suitable_for"] = ensure_list(filtered_data.get("suitable_for") or [])
#     filtered_data["famous_for"] = ensure_list(filtered_data.get("famous_for") or [])
#     filtered_data["best_months"] = ensure_list(filtered_data.get("best_months") or [])
#     filtered_data["nearby_attractions"] = ensure_list(filtered_data.get("nearby_attractions") or [])

#     # JSONB fields
#     filtered_data["entry_fee"] = dict(place_req.entry_fee.dict()) if place_req.entry_fee else {}
#     filtered_data["accessibility"] = dict(place_req.accessibility.dict()) if place_req.accessibility else {}

#     # Explicit lat/lng/rating cast
#     filtered_data["lat"] = float(src["lat"]) if src.get("lat") is not None else None
#     filtered_data["lng"] = float(src["lng"]) if src.get("lng") is not None else None
#     filtered_data["rating"] = float(src["rating"]) if src.get("rating") is not None else None

#     # System fields
#     filtered_data["place_id"] = place_id
#     # filtered_data["extras"] = extras
#     filtered_data["last_verified"] = filtered_data.get("last_verified") or datetime.utcnow().date()

#     # Embedding text
#     embedding_text = " ".join([
#         filtered_data.get("name", ""),
#         filtered_data.get("city", ""),
#         filtered_data.get("state", ""),
#         filtered_data.get("country", ""),
#         filtered_data.get("description", "")
#     ]).strip()

#     # Embedding generation
#     embedding_vec = None
#     try:
#         embedding_vec = get_embedding(embedding_text) if embedding_text else None
#         if embedding_vec is not None and len(embedding_vec) != 384:
#             raise ValueError("Embedding dimension mismatch; expected 384")
#     except Exception:
#         embedding_vec = None

#     filtered_data["embedding"] = embedding_vec

#     # Persist
#     place_obj = Places(**filtered_data)
#     db.add(place_obj)
#     try:
#         db.commit()
#     except Exception:
#         db.rollback()
#         existing_place = (
#             db.query(Places)
#             .filter(
#                 func.lower(func.trim(Places.name)) == func.lower(name),
#                 func.lower(func.trim(Places.city)) == func.lower(city),
#                 func.lower(func.trim(Places.state)) == func.lower(state),
#                 func.lower(func.trim(Places.country)) == func.lower(country),
#             )
#             .first()
#         )
#         if existing_place:
#             return {"message": "Entry already exists", "place_id": existing_place.place_id}
#         raise HTTPException(status_code=500, detail="Database error")

#     db.refresh(place_obj)
#     return {"message": "Place data inserted successfully", "place_id": place_id}

# @router.post("/bulk_create")
# def bulk_create_places(places_req: List[dict], db: Session = Depends(get_db)):
#     """
#     Accept a list of JSON objects, prevent duplicates,
#     insert unique places with auto-generated IDs,
#     and generate embeddings for each.
#     """

#     if not places_req:
#         raise HTTPException(status_code=400, detail="No data provided")

#     inserted = []
#     skipped = []

#     # --- Get last place_id once ---
#     last_place = db.query(Places).order_by(Places.id.desc()).first()
#     if not last_place or not last_place.place_id:
#         next_id_num = 1
#     else:
#         next_id_num = int(last_place.place_id.split("_")[1]) + 1

#     for place_req in places_req:
#         # --- Required defaults ---
#         for f in ["name", "city", "state", "country"]:
#             if f not in place_req or not str(place_req[f]).strip():
#                 skipped.append({"data": place_req, "reason": f"Missing required field: {f}"})
#                 break
#         else:  # only if all required fields are present
#             name = place_req["name"].strip()
#             city = place_req["city"].strip()
#             state = place_req["state"].strip()
#             country = place_req["country"].strip()

#             # --- Duplicate check ---
#             existing_place = (
#                 db.query(Places)
#                 .filter(
#                     Places.name.ilike(name),
#                     Places.city.ilike(city),
#                     Places.state.ilike(state),
#                     Places.country.ilike(country),
#                 )
#                 .first()
#             )
#             if existing_place:
#                 skipped.append({
#                     "data": place_req,
#                     "reason": "Entry already exists",
#                     "existing_place_id": existing_place.place_id,
#                 })
#                 continue

#             # --- Assign unique place_id ---
#             place_id = f"P_{next_id_num:05d}"
#             next_id_num += 1

#             # --- Filter valid DB columns ---
#             valid_columns = {c.name for c in Places.__table__.columns}
#             filtered_data = {}
#             extras = {}

#             for key, value in place_req.items():
#                 if key == "id":  # ignore incoming id
#                     continue
#                 if key in valid_columns:
#                     filtered_data[key] = value
#                 else:
#                     extras[key] = value

#             # --- Add system-generated fields ---
#             filtered_data["place_id"] = place_id
#             filtered_data["extras"] = extras
#             if "last_verified" not in filtered_data:
#                 filtered_data["last_verified"] = datetime.now().date()

#             # --- Generate embedding (use text representation for consistency) ---
#             embedding_text = f"{name}, {city}, {state}, {country}, {extras}"
#             filtered_data["embedding"] = get_embedding(embedding_text)

#             # --- Save to DB session ---
#             place_obj = Places(**filtered_data)
#             db.add(place_obj)
#             inserted.append({"place_id": place_id, "name": name, "city": city})

#     db.commit()

#     return {
#         "inserted_count": len(inserted),
#         "skipped_count": len(skipped),
#         "inserted": inserted,
#         "skipped": skipped,
#     }


