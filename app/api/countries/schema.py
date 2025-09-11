from pydantic import BaseModel, Field, field_validator, ValidationInfo 
from typing import Optional, List, Dict, Any
from datetime import date
from pydantic.config import ConfigDict
from enum import Enum

class CountryBase(BaseModel):
    name: str

class CountryCreate(CountryBase):
    pass

class CountryRead(CountryBase):
    id: int
    country_id: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class CountryUpdate(CountryBase):
    id: int

class CountryDelete(BaseModel):
    id: int
    is_active: bool