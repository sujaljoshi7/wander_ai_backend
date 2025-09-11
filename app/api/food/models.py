from sqlalchemy import Column, Integer, String, Text, Float, Date, DECIMAL, Numeric, ForeignKey, JSON, text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.mutable import MutableDict, MutableList
from datetime import datetime
from app.database import BaseModel

from app.database.db import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")  # portable JSON 

class Food(BaseModel):
    __tablename__ = "food"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)


# allow longer canonical IDs; enforce unique
    food_id = Column(String(64), unique=True, index=True, nullable=False)

    # core identity/location
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    city = Column(String(255), nullable=False, index=True)
    city_id = Column(String(64), ForeignKey('cities.city_id'), nullable=True, index=True)

    cuisine_type = Column(ARRAY(String), nullable=False, server_default="{}")  # Street Food, Fine Dining, Cafe, etc.

    rating = Column(Float, nullable=True)  # average rating, e.g., 4.5
    price_range = Column(String(50), nullable=True)  # e.g., "$", "$$", "$$$"

    food_type = Column(String(100), nullable=True, index=True)  # e.g., "Vegetarian", "Vegan", "Non-Vegetarian"

    restaurant_ids = Column(ARRAY(String), nullable=False, server_default="{}")

    restaurant_names = Column(ARRAY(String), nullable=False, server_default="{}")

    last_verified = Column(Date, nullable=True)

    notes = Column(Text, nullable=True)
