from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from app.database import BaseModel


from app.database.db import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")  # portable JSON 

class Country(BaseModel):
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    country_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, index=True)
