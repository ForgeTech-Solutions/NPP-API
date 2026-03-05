"""Pydantic schemas for User model."""
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime, date
from typing import Optional, List


# ── Pack info (embedded in UserOut) ──────────────────────────────────────

class QuotaInfo(BaseModel):
    """Rate-limit quota for FREE pack users."""
    requests_today: int
    requests_month: int
    limit_day: Optional[int]
    limit_month: Optional[int]
    remaining_today: Optional[int]
    remaining_month: Optional[int]
    reset_date: str  # ISO date of next daily reset (midnight GMT+1)


class PackDetail(BaseModel):
    """Detail of a subscription pack."""
    slug: str
    name: str
    target: str
    description: str
    features: List[str]
    limitations: List[str]
    rate_limit_day: Optional[int]
    rate_limit_month: Optional[int]
    requires_approval: bool


# ── User schemas ──────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    """Admin creates a user directly (approved immediately)."""
    password: str
    full_name: str
    role: str = "LECTEUR"
    pack: str = "FREE"
    organisation: Optional[str] = None
    phone: Optional[str] = None


class UserPublicSignup(UserBase):
    """Public signup — pending admin approval. No password required."""
    full_name: str
    organisation: str
    phone: Optional[str] = None
    message: Optional[str] = None
    pack: str = "FREE"


class UserUpdate(BaseModel):
    """Schema for updating a user (admin)."""
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    pack: Optional[str] = None
    is_active: Optional[bool] = None
    is_approved: Optional[bool] = None
    organisation: Optional[str] = None
    phone: Optional[str] = None


class UserOut(UserBase):
    """Full user output including pack and quota."""
    id: int
    full_name: str = ""
    role: str
    pack: str
    is_active: bool
    is_approved: bool
    organisation: Optional[str] = None
    phone: Optional[str] = None
    signup_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    pack_detail: Optional[PackDetail] = None
    quota: Optional[QuotaInfo] = None

    model_config = ConfigDict(from_attributes=True)


class UserListOut(UserBase):
    """Lightweight user output for list views."""
    id: int
    full_name: str = ""
    role: str
    pack: str
    is_active: bool
    is_approved: bool
    organisation: Optional[str] = None
    phone: Optional[str] = None
    requests_today: int
    requests_month: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Self-service schemas ──────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    """User changes their own password."""
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    """User updates their own profile (limited fields)."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    organisation: Optional[str] = None


class UserStatsOut(BaseModel):
    """User activity statistics."""
    email: str
    full_name: str
    pack: str
    pack_name: str
    organisation: Optional[str] = None
    # Quotas
    requests_today: int
    requests_month: int
    limit_day: Optional[int] = None
    limit_month: Optional[int] = None
    remaining_today: Optional[int] = None
    remaining_month: Optional[int] = None
    # Account
    is_active: bool
    is_approved: bool
    account_created: datetime
    account_age_days: int
    # Features
    available_features: List[str]


class DeleteAccountRequest(BaseModel):
    """User confirms account deletion with their password."""
    password: str
    confirm_email: EmailStr


# ── Auth tokens ───────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    """Schema for approving a user — optional password override."""
    pack: str = "FREE"
    password: Optional[str] = None  # If None, auto-generated


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    pack: str = "FREE"
    is_approved: bool = False

