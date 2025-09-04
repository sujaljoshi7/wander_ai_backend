from pydantic import BaseModel, Field, field_validator, ValidationInfo 
from typing import Optional, List, Dict, Any
from datetime import date
from enum import Enum

# Request schema
# class PlaceRequest(BaseModel):
#     name: str
#     city: str
#     state: str = None
#     country: str = None

# # Response schema
# class PlaceResponse(BaseModel):
#     id: int
#     place_id: str
#     name: str
#     city: str
#     state: str
#     country: str
#     lat: Optional[float] = None
#     lng: Optional[float] = None
#     type: Optional[str] = None
#     tags: Optional[List[str]] = None             # ✅ FIXED
#     description: Optional[str] = None
#     avg_visit_mins: Optional[int] = None
#     entry_fee: Optional[Dict[str, float]] = None # ✅ FIXED
#     open_hours: Optional[Dict[str, str]] = None  # ✅ FIXED
#     best_months: Optional[List[str]] = None      # ✅ FIXED
#     rating: Optional[float] = None
#     famous_for: Optional[List[str]] = None       # ✅ FIXED
#     accessibility: Optional[Dict[str, str]] = None
#     nearby_attractions: Optional[List[str]] = None
#     suitable_for: Optional[List[str]] = None
#     notes: Optional[str] = None
#     last_verified: Optional[date] = None
#     extras: Optional[Dict] = None

#     class Config:
#         orm_mode = True  # ✅ Needed for SQLAlchemy models






WEEKDAYS = ["mon","tue","wed","thu","fri","sat","sun"]

class EntryFee(BaseModel):
    currency: Optional[str] = "INR"
    adult: Optional[float] = 0
    child: Optional[float] = 0
    foreign: Optional[float] = 0

class Accessibility(BaseModel):
    wheelchair: Optional[bool] = None
    public_transport: Optional[bool] = None
    parking: Optional[bool] = None

class OpenHours(BaseModel):
    mon: Optional[List[List[str]]] = []
    tue: Optional[List[List[str]]] = []
    wed: Optional[List[List[str]]] = []
    thu: Optional[List[List[str]]] = []
    fri: Optional[List[List[str]]] = []
    sat: Optional[List[List[str]]] = []
    sun: Optional[List[List[str]]] = []
    notes: Optional[str] = ""

class PlaceCreate(BaseModel):
# core
    name: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)

    lat: Optional[float] = None
    lng: Optional[float] = None

    type: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    avg_visit_mins: Optional[int] = Field(default=60, ge=1, le=1440)

    entry_fee: Optional[EntryFee] = None

    # open_hours: {"mon":[["08:30","18:30"]], ... , "notes": "text"}
    open_hours: Optional[OpenHours] = None
    extras: Optional[Dict[str, Any]] = None
    best_months: Optional[List[str]] = None
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    famous_for: Optional[List[str]] = None
    accessibility: Optional[Accessibility] = None
    nearby_attractions: Optional[List[str]] = None
    suitable_for: Optional[List[str]] = None
    notes: Optional[str] = None
    last_verified: Optional[date] = None


# Validate weekday windows only
WEEKDAYS = ["mon","tue","wed","thu","fri","sat","sun"]

@field_validator("open_hours")
@classmethod
def validate_open_hours_weekdays(cls, v: dict[str, list[list[str]]] | None):
    if v is None:
        return v
    for day in WEEKDAYS:
        if day not in v:
            raise ValueError(f"open_hours missing weekday: {day}")
    windows = v[day]
    if not isinstance(windows, list):
        raise ValueError(f"open_hours[{day}] must be a list")
    for win in windows:
        if not (isinstance(win, list) and len(win) == 2):
            raise ValueError(f'open_hours[{day}] windows must be ["HH:MM","HH:MM"]')
        s, e = win
        if not (
            isinstance(s, str) and isinstance(e, str)
            and len(s) == 5 and len(e) == 5
            and s[2] == ":" and e[2] == ":"
        ):
            raise ValueError(f"open_hours[{day}] time format must be HH:MM")
# allow only weekdays and optional notes
    allowed = set(WEEKDAYS + ["notes"])
    extra = set(v.keys()) - allowed
    if extra:
        raise ValueError(f"open_hours has unknown keys: {sorted(extra)}")
    return v

@field_validator("open_hours")
@classmethod
def validate_open_hours_notes(cls, v: dict | None):
    if v is None:
        return v
    if "notes" in v and not isinstance(v["notes"], str):
        raise ValueError("open_hours.notes must be a string")
    return v