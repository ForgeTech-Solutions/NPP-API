"""User database model."""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Enum as SQLEnum
import enum
from app.db.base import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    ADMIN = "ADMIN"
    LECTEUR = "LECTEUR"


class PackType(str, enum.Enum):
    """Subscription pack enumeration."""
    FREE = "FREE"
    PRO = "PRO"
    INSTITUTIONNEL = "INSTITUTIONNEL"
    DEVELOPPEUR = "DEVELOPPEUR"


class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.LECTEUR)

    # Identity
    full_name = Column(String(255), nullable=False, default="")
    phone = Column(String(50), nullable=True)
    signup_message = Column(String(1000), nullable=True)

    # Pack & approval
    pack = Column(SQLEnum(PackType), nullable=False, default=PackType.FREE)
    is_active = Column(Boolean, default=True, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)  # Admin must approve

    # Rate limiting (FREE pack only)
    requests_today = Column(Integer, default=0, nullable=False)
    requests_month = Column(Integer, default=0, nullable=False)
    last_request_date = Column(Date, nullable=True)

    # Organisation / context (optional enrichment)
    organisation = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role}, pack={self.pack})>"
