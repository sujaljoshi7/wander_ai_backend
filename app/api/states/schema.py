from pydantic import BaseModel, Field, field_validator, ValidationInfo 
from typing import Optional, List, Dict, Any
from datetime import date
from pydantic.config import ConfigDict
from enum import Enum

class CountryRead(BaseModel):
    country_id: str
    name: str
    model_config = ConfigDict(from_attributes=True)

class StateBase(BaseModel):
    name: str
    country_id: str

class StateCreate(StateBase):
    pass

class StateRead(StateBase):
    id: int
    state_id: str
    country_id: str
    is_active: bool
    country: CountryRead
    model_config = ConfigDict(from_attributes=True)

class StateUpdate(StateBase):
    id: int

class StateDelete(BaseModel):
    id: int
    is_active: bool