"""API Key database model."""
import hashlib
import secrets
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from app.db.base import Base


def generate_api_key() -> str:
    """Generate a random API key with npp_sk_ prefix."""
    return f"npp_sk_{secrets.token_hex(32)}"


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of the raw API key (stored in DB)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKey(Base):
    """Persistent API key for machine-to-machine integration."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # e.g. "Mon script ERP"
    key_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256
    key_prefix = Column(String(20), nullable=False)  # "npp_sk_****...a7b8" for display
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    last_used_ip = Column(String(45), nullable=True)
    requests_count = Column(BigInteger, default=0, nullable=False)

    # Relationship
    user = relationship("User", backref="api_keys", lazy="selectin")

    @staticmethod
    def mask_key(raw_key: str) -> str:
        """Return masked version: npp_sk_****...last4"""
        return f"{raw_key[:7]}****...{raw_key[-4:]}"

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, user_id={self.user_id}, prefix={self.key_prefix})>"
