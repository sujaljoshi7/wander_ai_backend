from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from app.database import BaseModel
from sqlalchemy.orm import relationship

from app.database.db import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")  # portable JSON 

class State(BaseModel):
    __tablename__ = "states"
    id = Column(Integer, primary_key=True, autoincrement=True)
    state_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    country_id = Column(String(64), ForeignKey('countries.country_id'), nullable=True, index=True)

    country = relationship("Country", cascade="all, delete")
