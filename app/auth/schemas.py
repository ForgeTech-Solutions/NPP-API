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

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "requests_today": 12,
            "requests_month": 345,
            "limit_day": 100,
            "limit_month": 1000,
            "remaining_today": 88,
            "remaining_month": 655,
            "reset_date": "2026-03-06",
        }
    })


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

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "slug": "PRO",
            "name": "Pro",
            "target": "Pharmacies & Grossistes",
            "description": "Officines et grossistes répartiteurs.",
            "features": [
                "Recherche par DCI, marque ou code AMM",
                "Export CSV pour la gestion de stock",
                "Requêtes illimitées",
            ],
            "limitations": [],
            "rate_limit_day": None,
            "rate_limit_month": None,
            "requires_approval": True,
        }
    })


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

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "pharmacie.benali@email.dz",
            "password": "SecureP@ss2026!",
            "full_name": "Dr. Benali Karim",
            "role": "LECTEUR",
            "pack": "PRO",
            "organisation": "Pharmacie Centrale Benali",
            "phone": "+213 555 123 456",
        }
    })


class UserPublicSignup(UserBase):
    """Public signup — pending admin approval. No password required."""
    full_name: str
    organisation: str
    phone: Optional[str] = None
    message: Optional[str] = None
    pack: str = "FREE"

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "contact@clinique-alger.dz",
            "full_name": "Dr. Amira Khelifi",
            "organisation": "Clinique El Azhar — Alger",
            "phone": "+213 550 987 654",
            "message": "Nous souhaitons intégrer la nomenclature dans notre système HIS.",
            "pack": "INSTITUTIONNEL",
        }
    })


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

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "pack": "PRO",
            "is_approved": True,
            "organisation": "Pharmacie Centrale Benali — Blida",
        }
    })


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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 3,
                "email": "pharmacie.benali@email.dz",
                "full_name": "Dr. Benali Karim",
                "role": "LECTEUR",
                "pack": "PRO",
                "is_active": True,
                "is_approved": True,
                "organisation": "Pharmacie Centrale Benali",
                "phone": "+213 555 123 456",
                "signup_message": None,
                "created_at": "2026-02-15T10:30:00",
                "updated_at": "2026-03-01T14:22:00",
                "pack_detail": {
                    "slug": "PRO",
                    "name": "Pro",
                    "target": "Pharmacies & Grossistes",
                    "description": "Officines et grossistes répartiteurs.",
                    "features": ["Recherche par DCI, marque ou code AMM", "Export CSV", "Requêtes illimitées"],
                    "limitations": [],
                    "rate_limit_day": None,
                    "rate_limit_month": None,
                    "requires_approval": True,
                },
                "quota": None,
            }
        },
    )


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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 3,
                "email": "pharmacie.benali@email.dz",
                "full_name": "Dr. Benali Karim",
                "role": "LECTEUR",
                "pack": "PRO",
                "is_active": True,
                "is_approved": True,
                "organisation": "Pharmacie Centrale Benali",
                "phone": "+213 555 123 456",
                "requests_today": 42,
                "requests_month": 1250,
                "created_at": "2026-02-15T10:30:00",
            }
        },
    )


# ── Self-service schemas ──────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    """User changes their own password."""
    current_password: str
    new_password: str

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "current_password": "AncienMotDePasse123!",
            "new_password": "NouveauSecure@2026",
        }
    })


class UpdateProfileRequest(BaseModel):
    """User updates their own profile (limited fields)."""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    organisation: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "full_name": "Dr. Benali Karim",
            "phone": "+213 555 999 888",
            "organisation": "Pharmacie Centrale Benali — Blida",
        }
    })


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

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "pharmacie.benali@email.dz",
            "full_name": "Dr. Benali Karim",
            "pack": "PRO",
            "pack_name": "Pro",
            "organisation": "Pharmacie Centrale Benali",
            "requests_today": 42,
            "requests_month": 1250,
            "limit_day": None,
            "limit_month": None,
            "remaining_today": None,
            "remaining_month": None,
            "is_active": True,
            "is_approved": True,
            "account_created": "2026-02-15T10:30:00",
            "account_age_days": 19,
            "available_features": [
                "search_basic", "medicament_detail", "filters_advanced",
                "group_by_dci", "status_enregistrement", "retraits_non_renouveles",
                "export_csv",
            ],
        }
    })


class DeleteAccountRequest(BaseModel):
    """User confirms account deletion with their password."""
    password: str
    confirm_email: EmailStr

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "password": "MonMotDePasse123!",
            "confirm_email": "pharmacie.benali@email.dz",
        }
    })


# ── Auth tokens ───────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    """Schema for approving a user — optional password override."""
    pack: str = "FREE"
    password: Optional[str] = None  # If None, auto-generated

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "pack": "PRO",
            "password": None,
        }
    })


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "admin@nomenclature.dz",
            "password": "Admin2025!",
        }
    })


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    pack: str = "FREE"
    is_approved: bool = False

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBub21lbmNsYXR1cmUuZHoiLCJleHAiOjE3NDEyNzI4MDB9.abc123",
            "token_type": "bearer",
            "pack": "DEVELOPPEUR",
            "is_approved": True,
        }
    })

