"""Security utilities: password hashing, JWT verification, pack guards, rate limiter."""
from datetime import datetime, timedelta, date, timezone
from typing import Optional, List
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.packs import PACK_LIMITS, PACK_FEATURES
from app.db.session import get_db

# ── Constants ──────────────────────────────────────────────────────────────
ALGIERS_TZ = ZoneInfo("Africa/Algiers")  # GMT+1

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# ── Password helpers ───────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ── JWT helpers ────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── Core auth dependencies ─────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Validate JWT and return the authenticated user."""
    from app.auth.models import User

    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise exc

    email: str = payload.get("sub")
    if email is None:
        raise exc

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise exc

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending admin approval",
        )

    return user


async def get_current_admin(current_user=Depends(get_current_user)):
    """Require ADMIN role."""
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user


# ── Rate limiter (FREE pack only) ──────────────────────────────────────────

async def _apply_rate_limit(user, db: AsyncSession) -> None:
    """Increment counters for FREE pack and raise 429 if limit exceeded."""
    if user.pack != "FREE":
        return

    limits = PACK_LIMITS["FREE"]
    day_limit: int = limits["requests_per_day"]
    month_limit: int = limits["requests_per_month"]

    today_algiers: date = datetime.now(ALGIERS_TZ).date()

    # Reset daily counter if day changed
    if user.last_request_date != today_algiers:
        user.requests_today = 0
        user.last_request_date = today_algiers

        # Reset monthly counter if month changed
        if (
            user.last_request_date is None
            or user.last_request_date.month != today_algiers.month
            or user.last_request_date.year != today_algiers.year
        ):
            user.requests_month = 0

    # Check limits BEFORE incrementing
    if user.requests_today >= day_limit:
        next_reset = (today_algiers + timedelta(days=1)).isoformat()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "daily_limit_exceeded",
                "message": f"Limite journalière atteinte ({day_limit} requêtes/jour — pack FREE).",
                "limit_day": day_limit,
                "requests_today": user.requests_today,
                "remaining_today": 0,
                "reset_at": f"{next_reset}T00:00:00+01:00",
                "upgrade_hint": "Contactez l'administrateur pour passer au pack PRO.",
            },
        )

    if user.requests_month >= month_limit:
        first_next_month = today_algiers.replace(day=1)
        if today_algiers.month == 12:
            first_next_month = first_next_month.replace(year=today_algiers.year + 1, month=1)
        else:
            first_next_month = first_next_month.replace(month=today_algiers.month + 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "monthly_limit_exceeded",
                "message": f"Limite mensuelle atteinte ({month_limit} requêtes/mois — pack FREE).",
                "limit_month": month_limit,
                "requests_month": user.requests_month,
                "remaining_month": 0,
                "reset_at": f"{first_next_month.isoformat()}T00:00:00+01:00",
                "upgrade_hint": "Contactez l'administrateur pour passer au pack PRO.",
            },
        )

    # Increment and persist
    user.requests_today += 1
    user.requests_month += 1
    db.add(user)
    await db.commit()


# ── Pack guard dependency factory ─────────────────────────────────────────

def require_pack(allowed_packs: List[str], feature_key: Optional[str] = None):
    """
    Dependency factory: ensure user's pack is in `allowed_packs`.
    Also applies rate limiting for FREE pack users.

    Usage:
        Depends(require_pack(["PRO", "INSTITUTIONNEL", "DEVELOPPEUR"]))
    """
    async def dependency(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        # Apply rate limit first (only relevant for FREE)
        await _apply_rate_limit(current_user, db)

        if current_user.role == "ADMIN":
            return current_user  # Admin bypasses pack restrictions

        if current_user.pack not in allowed_packs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "pack_required",
                    "message": f"Cette fonctionnalité requiert l'un des packs suivants : {', '.join(allowed_packs)}.",
                    "current_pack": current_user.pack,
                    "required_packs": allowed_packs,
                    "upgrade_hint": "Contactez l'administrateur pour changer votre pack.",
                },
            )
        return current_user

    return dependency


def require_any_pack():
    """Dependency: any approved user (all packs). Applies rate limit for FREE."""
    async def dependency(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        await _apply_rate_limit(current_user, db)
        return current_user

    return dependency

