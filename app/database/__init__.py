from sqlalchemy import Column, DateTime, Boolean
from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base, Session
from app.database.db import Base
from typing import Optional
# Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    def save(self, db: Session):
        self.created_at = datetime.now(timezone.utc)
        db.add(self)
        db.commit()
        db.refresh(self)

    def update(self, db: Session, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc)
        db.add(self)
        db.commit()
        db.refresh(self)

    def soft_delete(self, db: Session, is_active: bool, updated_by: Optional[int] = None):
        self.is_active = is_active
        # self.deleted_at = None if is_active else datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
 
        if hasattr(self, "updated_by") and updated_by is not None:
            self.updated_by = updated_by
        db.add(self)
        db.commit()
        db.refresh(self)

    def update_last_login(self, db: Session):
        self.last_signed_in_at = datetime.now(timezone.utc)
        db.add(self)
        db.commit()
        db.refresh(self)

    def commit(self, db: Session):
        db.commit()
