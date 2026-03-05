"""ServiceMeta model — stores persistent service metadata (first start, etc.)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.db.base import Base


class ServiceMeta(Base):
    """Single-row table tracking service lifecycle metadata."""

    __tablename__ = "service_meta"

    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    value = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
