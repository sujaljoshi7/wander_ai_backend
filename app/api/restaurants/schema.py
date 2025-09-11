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

class RestaurantBase(BaseModel):
    name: str
    description: str = None
    city: str
    city_id: str = None
    lat: float
    lng: float  
    cuisine_type: List[str] = Field(default_factory=list)
    price_range: str = None
    must_try_dishes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    food_type: str = None
    notes: str = None

class RestaurantCreate(RestaurantBase):
    pass

class RestaurantRead(RestaurantBase):
    id: int
    # restaurant_id: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class RestaurantUpdate(RestaurantBase):
    id: int

class RestaurantDelete(BaseModel):
    id: int
    is_active: bool