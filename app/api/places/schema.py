from pydantic import BaseModel, Field, field_validator, ValidationInfo, validator
from typing import Optional, List, Dict, Any, Union
from datetime import date, datetime
from enum import Enum
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

class EntryFee(BaseModel):
    adult: Optional[float] = None
    child: Optional[float] = None
    senior: Optional[float] = None

class Accessibility(BaseModel):
    wheelchair_accessible: Optional[bool] = None
    parking_available: Optional[bool] = None
    public_transport: Optional[bool] = None

class PlaceBase(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    country: str
    state: str
    city: str
    country_id: Optional[str] = None
    state_id: Optional[str] = None
    city_id: Optional[str] = None
    lat: float
    lng: float
    avg_visit_mins: int
    tags: List[str] = Field(default_factory=list)
    suitable_for: List[str] = Field(default_factory=list)
    famous_for: List[str] = Field(default_factory=list)
    entry_fee: EntryFee = Field(default_factory=EntryFee)
    accessibility: Accessibility = Field(default_factory=Accessibility)
    currency: Optional[str] = None

    avg_cost_per_person: Optional[float] = None
    open_hours: Dict[str, List[List[str]]] = Field(default_factory=dict)
    best_months: List[str] = Field(default_factory=list)
    best_time_of_day_to_visit: Optional[List[List[str]]] = Field(default_factory=list)
    rating: Optional[float] = None
    nearby_attractions: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    last_verified: Optional[date] = None

    @validator('last_verified', pre=True, always=True)
    def default_last_verified(cls, v):
        return v or datetime.utcnow().date()


class PlaceCreate(PlaceBase):
    pass

class PlaceUpdate(PlaceBase):
    id: int

class PlaceRead(BaseModel):
    id: int
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    country_id: Optional[str] = None
    state_id: Optional[str] = None
    city_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    avg_visit_mins: Optional[int] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    suitable_for: Optional[List[str]] = Field(default_factory=list)
    famous_for: Optional[List[str]] = Field(default_factory=list)
    entry_fee: Optional[EntryFee] = Field(default_factory=EntryFee)
    accessibility: Optional[Accessibility] = Field(default_factory=Accessibility)
    currency: Optional[str] = None

    avg_cost_per_person: Optional[float] = None
    open_hours: Optional[Dict[str, List[List[str]]]] = Field(default_factory=dict)
    best_months: Optional[List[str]] = Field(default_factory=list)
    best_time_of_day_to_visit: Optional[List[List[str]]] = Field(default_factory=list)
    rating: Optional[float] = None
    nearby_attractions: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = None
    last_verified: Optional[date] = None

    @validator('last_verified', pre=True, always=True)
    def default_last_verified(cls, v):
        return v or datetime.utcnow().date()

    class Config:
        orm_mode = True  # Needed for SQLAlchemy models

class PlaceDelete(BaseModel):
    id: int
    is_active: bool

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






# WEEKDAYS = ["mon","tue","wed","thu","fri","sat","sun"]

# class EntryFee(BaseModel):
#     currency: Optional[str] = "INR"
#     adult: Optional[float] = 0
#     child: Optional[float] = 0
#     foreign: Optional[float] = 0

# class Accessibility(BaseModel):
#     wheelchair: Optional[bool] = None
#     public_transport: Optional[bool] = None
#     parking: Optional[bool] = None

# class OpenHours(BaseModel):
#     mon: Optional[List[List[str]]] = []
#     tue: Optional[List[List[str]]] = []
#     wed: Optional[List[List[str]]] = []
#     thu: Optional[List[List[str]]] = []
#     fri: Optional[List[List[str]]] = []
#     sat: Optional[List[List[str]]] = []
#     sun: Optional[List[List[str]]] = []
#     notes: Optional[str] = ""

# class PlaceCreate(BaseModel):
# # core
#     name: str = Field(..., min_length=1)
#     city: str = Field(..., min_length=1)
#     state: str = Field(..., min_length=1)
#     country: str = Field(..., min_length=1)

#     lat: Optional[float] = None
#     lng: Optional[float] = None

#     type: Optional[str] = None
#     tags: Optional[List[str]] = None
#     description: Optional[str] = None
#     avg_visit_mins: Optional[int] = Field(default=60, ge=1, le=1440)

#     entry_fee: Optional[EntryFee] = None

#     # open_hours: {"mon":[["08:30","18:30"]], ... , "notes": "text"}
#     open_hours: Optional[OpenHours] = None
#     extras: Optional[Dict[str, Any]] = None
#     best_months: Optional[List[str]] = None
#     rating: Optional[float] = Field(default=None, ge=0, le=5)
#     famous_for: Optional[List[str]] = None
#     accessibility: Optional[Accessibility] = None
#     nearby_attractions: Optional[List[str]] = None
#     suitable_for: Optional[List[str]] = None
#     notes: Optional[str] = None
#     last_verified: Optional[date] = None


# # Validate weekday windows only
# WEEKDAYS = ["mon","tue","wed","thu","fri","sat","sun"]

# @field_validator("open_hours")
# @classmethod
# def validate_open_hours_weekdays(cls, v: dict[str, list[list[str]]] | None):
#     if v is None:
#         return v
#     for day in WEEKDAYS:
#         if day not in v:
#             raise ValueError(f"open_hours missing weekday: {day}")
#     windows = v[day]
#     if not isinstance(windows, list):
#         raise ValueError(f"open_hours[{day}] must be a list")
#     for win in windows:
#         if not (isinstance(win, list) and len(win) == 2):
#             raise ValueError(f'open_hours[{day}] windows must be ["HH:MM","HH:MM"]')
#         s, e = win
#         if not (
#             isinstance(s, str) and isinstance(e, str)
#             and len(s) == 5 and len(e) == 5
#             and s[2] == ":" and e[2] == ":"
#         ):
#             raise ValueError(f"open_hours[{day}] time format must be HH:MM")
# # allow only weekdays and optional notes
#     allowed = set(WEEKDAYS + ["notes"])
#     extra = set(v.keys()) - allowed
#     if extra:
#         raise ValueError(f"open_hours has unknown keys: {sorted(extra)}")
#     return v

# @field_validator("open_hours")
# @classmethod
# def validate_open_hours_notes(cls, v: dict | None):
#     if v is None:
#         return v
#     if "notes" in v and not isinstance(v["notes"], str):
#         raise ValueError("open_hours.notes must be a string")
#     return v