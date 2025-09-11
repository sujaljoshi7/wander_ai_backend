from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time, timezone
from app.database.db import get_db
from app.api.states.models import State
from typing import List, Optional, Dict, Any
from app.utils.embeddings import get_embedding
import subprocess
from sqlalchemy import text, func, Table, MetaData, create_engine
import json, math, httpx, subprocess
from app.api.states.schema import StateCreate, StateRead, StateUpdate, StateDelete
import os
from app.utils.helper import CommonResponse
from app.utils.searching import apply_searching
from app.utils.sorting import apply_sorting
from app.utils.pagination import get_pagination_metadata
from sqlalchemy.exc import SQLAlchemyError
from app.utils.helper import safe_db_operation

router = APIRouter(prefix="/state", tags=["States"])

def generate_state_id(db: Session) -> str:
    last_place = db.query(State).order_by(State.id.desc()).first()
    if not last_place or not last_place.state_id:
        return "state_00001"
    last_num = int(last_place.state_id.split("_")[1])
    return f"state_{last_num+1:05d}"



@router.post("/create")
@safe_db_operation("CreateState")
def create_state(state_req: StateCreate, db: Session = Depends(get_db)):
    """
    Accept JSON, ignore provided id, auto-generate country_id,
    prevent duplicate entries, and store embeddings.
    """


    # --- Duplicate check ---
    existing_state = (
        db.query(State)
        .filter(
            State.name.ilike(state_req.name), State.country_id == state_req.country_id
        )
        .first()
    )
    if existing_state:
        # return {"message": "State already exists", "is_success": False}
        return CommonResponse(
            is_success=False,
            message="State already exists",
            status_code=201
        )

    # --- Generate new place_id ---
    state_id = generate_state_id(db)

    # --- Prepare data ---
    data = state_req.model_dump()  # ignore incoming id
    data["state_id"] = state_id
    # data["last_verified"] = data.get("last_verified", datetime.now(timezone.utc).date())

    state = State(**data)
    db.add(state)
    db.commit()
    db.refresh(state)
    
    # return {"message": "State data inserted successfully", "is_success": True}
    return CommonResponse(
            is_success=True,
            message="State data inserted successfully",
            status_code=201
        )


@router.get("/get_all_states", response_model=CommonResponse[List[StateRead]])
@safe_db_operation("GetAllStates")
def get_all_states(
    is_active: Optional[bool] = Query(None, description="Filter by active (true)/inactive (false) status"),
    country_id: Optional[str] = Query(None, description="Filter by country_id"),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
    ):

    base_query = db.query(State)

    if is_active is not None:
        base_query = base_query.filter(State.is_active == bool(is_active))

    if country_id is not None:
        base_query = base_query.filter(State.country_id == country_id)

    # Apply search
    base_query = apply_searching(base_query, State, ["name"], search)

    total_count = base_query.count()

    # Apply sorting
    base_query = apply_sorting(base_query, State, sort_by, sort_order)
    total_count = base_query.count()
    

    # Apply pagination if both page and page_size provided
    if page and page_size:
        skip = (page - 1) * page_size
        base_query = base_query.offset(skip).limit(page_size)
        pagination = get_pagination_metadata(total_count, skip, page_size)
    else:
        pagination = None

    states = base_query.all()

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="States fetched successfully",
        is_success=True,
        result=states,
        pagination=pagination
    )

@router.get("/get_state/{state_id}", response_model=CommonResponse[StateRead])
@safe_db_operation("GetState")
def get_country(
    state_id : int,
    db: Session = Depends(get_db)
    ):

    base_query = db.query(State).filter(State.id == state_id)
    state = base_query.first()

    if not state:
        return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="No state found",
        is_success=False,
        result=state
    )

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="State fetched successfully",
        is_success=True,
        result=state
    )

@router.put("/update_state", response_model=CommonResponse[StateUpdate])
@safe_db_operation("UpdateState")
def update_state(update: StateUpdate,
                  db: Session = Depends(get_db)):
    # 1. First check if user exists
    state_update = db.query(State).filter(State.id == update.id).first()
    if not state_update:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="State not found",
            is_success=False,
            result=None,
        )

    # 2. Check if course exists
    existing_state = db.query(State).filter(
        State.name == update.name, 
        State.id != update.id
        ).first()
    if existing_state:
        return CommonResponse.response_handler(
            status_code=status.HTTP_200_OK,
            message="State with this name already exists.",
            is_success=False,
            result=None
        )


    update_data = update.dict(exclude={'id'})

    state_update.update(db, **update_data)

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message="State updated successfully",
        is_success=True,
        result=None
    )

    
@router.patch("/delete_state", response_model=CommonResponse,
               status_code=status.HTTP_200_OK)
@safe_db_operation("DeleteState")
def delete_state(update: StateDelete, db: Session = Depends(get_db)):

    state = db.query(State).filter(State.id == update.id).first()
    if not state:
        return CommonResponse.response_handler(
            status_code=status.HTTP_404_NOT_FOUND,
            message="State not found",
            result=None,
            is_success=False
        )

    state.update(db,is_active = update.is_active)

    if update.is_active:
        message = "State restored successfully"
    else:
        message = "State deleted successfully"

    return CommonResponse.response_handler(
        status_code=status.HTTP_200_OK,
        message=message,
        is_success=True,
        result=None
    )