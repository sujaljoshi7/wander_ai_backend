from sqlalchemy import Column, Integer, String, Text, Float, Date, DECIMAL, Numeric, ForeignKey, JSON, text, DateTime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.mutable import MutableDict, MutableList
from datetime import datetime


from app.database.db import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")  # portable JSON 

class Places(Base):
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)


# allow longer canonical IDs; enforce unique
    place_id = Column(String(64), unique=True, index=True, nullable=False)

    # core identity/location
    name = Column(String(255), nullable=False, index=True)
    city = Column(String(255), nullable=False, index=True)
    state = Column(String(255), nullable=False)
    country = Column(String(255), nullable=False, index=True)

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

    # schedule fields
    # open_hours structure: {"mon":[["08:30","18:30"]], "tue":[...], ...}
    open_hours = Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")
    best_months = Column(
        ARRAY(String), nullable=False, server_default="{}"
    )  # e.g., ["Nov","Dec",...]
    # optional numeric month map can live in extras.season_score

    # quality/meta
    rating = Column(Numeric(3, 2), nullable=True)  # supports e.g., 4.75
    nearby_attractions = Column(ARRAY(String), nullable=False, server_default="{}")
    notes = Column(Text, nullable=True)
    last_verified = Column(Date, nullable=False, index=True)

    # catch‑all for optional/evolving fields (policies, season_score, showtimes, etc.)
    extras = Column(MutableDict.as_mutable(JSONB), nullable=False, server_default="{}")

    # vector for retrieval (size must match your embedding model, e.g., 384 for MiniLM)
    embedding = Column(Vector(384), nullable=True)

    # optional: full‑text search materialized separately if needed
    # search_text TSVECTOR can be added via Alembic migration + triggers

class ItineraryRequest(Base):
    __tablename__ = "itinerary_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    city = Column(String(120), nullable=False, index=True)
    days = Column(Integer, nullable=False)
    suitable_for = Column(String(64), nullable=True, index=True)
    version = Column(String(32), nullable=False, default="v1.0.0")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    # Optional: user_id, trip_month, transport_mode, etc.

    candidates = relationship("ItineraryCandidate", back_populates="request", cascade="all, delete-orphan")
    result = relationship("ItineraryResult", uselist=False, back_populates="request", cascade="all, delete-orphan")
    model_ios = relationship("ItineraryModelIO", back_populates="request", cascade="all, delete-orphan")
    feedback = relationship("ItineraryFeedback", back_populates="request", cascade="all, delete-orphan")

class ItineraryCandidate(Base):
    __tablename__ = "itinerary_candidates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    itinerary_request_id = Column(Integer, ForeignKey("itinerary_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id = Column(String(64), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    avg_visit_mins = Column(Integer, nullable=False)
    rating = Column(Float, nullable=True)
    hop_from_city_min = Column(Integer, nullable=True)
    distance_from_city_km = Column(Float, nullable=True)
    city = Column(String(120), nullable=True)

    request = relationship("ItineraryRequest", back_populates="candidates")

class ItineraryResult(Base):
    __tablename__ = "itinerary_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    itinerary_request_id = Column(Integer, ForeignKey("itinerary_requests.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    itinerary_json = Column(JSONVariant, nullable=False)  # final itinerary
    auto_params_json = Column(JSONVariant, nullable=False)  # radius, budgets, speeds, etc.
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    request = relationship("ItineraryRequest", back_populates="result")

class ItineraryModelIO(Base):
    __tablename__ = "itinerary_model_io"
    id = Column(Integer, primary_key=True, autoincrement=True)
    itinerary_request_id = Column(Integer, ForeignKey("itinerary_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(64), nullable=False)  # e.g., "ai_finisher"
    prompt_text = Column(JSONVariant, nullable=False)  # store as JSON to avoid encoding issues
    raw_response_text = Column(JSONVariant, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    request = relationship("ItineraryRequest", back_populates="model_ios")

class ItineraryFeedback(Base):
    __tablename__ = "itinerary_feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    itinerary_request_id = Column(Integer, ForeignKey("itinerary_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    day = Column(Integer, nullable=True)
    place_id = Column(String(64), nullable=True)
    signal = Column(String(32), nullable=False)  # "thumbs_up", "thumbs_down", "edited"
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    request = relationship("ItineraryRequest", back_populates="feedback")
