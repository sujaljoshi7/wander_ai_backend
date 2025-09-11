from pydantic import BaseModel, Field, field_validator, ValidationInfo 
from typing import Optional, List, Dict, Any
from datetime import date
from pydantic.config import ConfigDict
from enum import Enum

class CountryRead(BaseModel):
    country_id: str
    name: str
    model_config = ConfigDict(from_attributes=True)

class StateRead(BaseModel):
    id: int
    state_id: str
    name: str
    country_id: str
    is_active: bool
    country: CountryRead
    model_config = ConfigDict(from_attributes=True)

class CityBase(BaseModel):
    name: str
    state_id: str
    country_id: str

class CityCreate(CityBase):
    pass

class CityRead(CityBase):
    id: int
    city_id: str
    state_id: str
    country_id: str
    is_active: bool
    state: StateRead
    model_config = ConfigDict(from_attributes=True)

class CityUpdate(CityBase):
    id: int

class CityDelete(BaseModel):
    id: int
    is_active: bool