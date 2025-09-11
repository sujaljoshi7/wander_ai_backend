from sqlalchemy import Column, Integer, String, Text, Float, Date, DECIMAL, Numeric, ForeignKey, JSON, text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.mutable import MutableDict, MutableList
from datetime import datetime
from app.database import BaseModel

from app.database.db import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")  # portable JSON 

class Restaurants(BaseModel):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)


# allow longer canonical IDs; enforce unique
    restaurant_id = Column(String(64), unique=True, index=True, nullable=False)

    # core identity/location
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    city = Column(String(255), nullable=False, index=True)
    city_id = Column(String(64), ForeignKey('cities.city_id'), nullable=True, index=True)

    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    cuisine_type = Column(ARRAY(String), nullable=False, server_default="{}")  # Street, Fine-Dine, Cafe, etc
    price_range = Column(String(50), nullable=True)  # e.g., "$", "$$", "$$$"

    must_try_dishes = Column(ARRAY(String), nullable=False, server_default="{}")

    tags = Column(ARRAY(String), nullable=False, server_default="{}")  # empty array default

    food_type = Column(String(100), nullable=True, index=True)  # e.g., "Vegetarian", "Vegan", "Non-Vegetarian"

    notes = Column(Text, nullable=True)

    last_verified = Column(Date, nullable=True)