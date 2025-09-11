from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship


from app.database.db import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")  # portable JSON 


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
