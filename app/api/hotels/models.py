from sqlalchemy import Column, Integer, String, Text, Float, Date, DECIMAL, Numeric, ForeignKey, JSON, text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.mutable import MutableDict, MutableList
from datetime import datetime
from app.database import BaseModel

from app.database.db import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")  # portable JSON 

class Hotels(BaseModel):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)


# allow longer canonical IDs; enforce unique
    hotel_id = Column(String(64), unique=True, index=True, nullable=False)

    # core identity/location
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    city = Column(String(255), nullable=False, index=True)
    city_id = Column(String(64), ForeignKey('cities.city_id'), nullable=True, index=True)
    address = Column(Text, nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    price_per_night = Column(Float, nullable=True)
    
    tags = Column(ARRAY(String), nullable=False, server_default="{}")  # empty array default

    notes = Column(Text, nullable=True)

    last_verified = Column(Date, nullable=True)