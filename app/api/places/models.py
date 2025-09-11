from sqlalchemy import Column, Integer, String, Text, Float, Date, DECIMAL, Numeric, ForeignKey, JSON, text, DateTime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.mutable import MutableDict, MutableList
from datetime import datetime
from app.database import BaseModel

from app.database.db import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")  # portable JSON 

class Places(BaseModel):
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)


# allow longer canonical IDs; enforce unique
    place_id = Column(String(64), unique=True, index=True, nullable=False)

    # core identity/location
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), nullable=False, index=True)
    state = Column(String(255), nullable=False)
    country = Column(String(255), nullable=False, index=True)
    city_id = Column(String(64), ForeignKey('cities.city_id'), nullable=True, index=True)
    state_id = Column(String(64), ForeignKey('states.state_id'), nullable=True, index=True)
    country_id = Column(String(64), ForeignKey('countries.country_id'), nullable=True, index=True)

    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    # taxonomy
    type = Column(String(100), nullable=False, index=True)
    tags = Column(ARRAY(String), nullable=False, server_default="{}")  # empty array default
    suitable_for = Column(ARRAY(String), nullable=False, server_default="{}")
    famous_for = Column(ARRAY(String), nullable=False, server_default="{}")

    # content
    description = Column(Text, nullable=True)
    avg_visit_mins = Column(Integer, nullable=False)
    # fees and access
    entry_fee = Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    accessibility = Column(
        MutableDict.as_mutable(JSONB), nullable=False, server_default="{}"
    )

    currency = Column(String(10), nullable=True)  # e.g., "USD", "INR"

    # schedule fields
    # open_hours structure: {"mon":[["08:30","18:30"]], "tue":[...], ...}
    avg_cost_per_person = Column(Numeric(10, 2), nullable=True)
    open_hours = Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    best_months = Column(
        ARRAY(String), nullable=False, server_default="{}"
    )  # e.g., ["Nov","Dec",...]
    # optional numeric month map can live in extras.season_score
    # best_time_of_day_to_visit = Column(ARRAY(String, dimensions=2), nullable=True, server_default="{}")
    
    best_time_of_day_to_visit = Column(MutableList.as_mutable(JSONB), nullable=True, server_default="[]")

    # quality/meta
    rating = Column(Numeric(3, 2), nullable=True)  # supports e.g., 4.75
    nearby_attractions = Column(ARRAY(String), nullable=False, server_default="{}")
    notes = Column(Text, nullable=True)
    last_verified = Column(Date, nullable=False, index=True)


    # vector for retrieval (size must match your embedding model, e.g., 384 for MiniLM)
    embedding = Column(Vector(384), nullable=True)

    # optional: full‑text search materialized separately if needed
    # search_text TSVECTOR can be added via Alembic migration + triggers