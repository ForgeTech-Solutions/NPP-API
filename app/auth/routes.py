"""Authentication routes."""
from datetime import datetime
from zoneinfo import ZoneInfo
import secrets as _secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.schemas import (
    Token, UserOut, UserCreate, UserPublicSignup,
    ChangePasswordRequest, UpdateProfileRequest, UserStatsOut, DeleteAccountRequest,
)
from app.auth.models import User, PackType
from app.auth.jwt import create_user_token
from app.core.security import verify_password, get_password_hash, get_current_user
from app.core.packs import PACK_CATALOG, PACK_LIMITS, PACK_FEATURES
from app.db.session import get_db

ALGIERS_TZ = ZoneInfo("Africa/Algiers")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _build_user_out(user: User) -> UserOut:
    """Build enriched UserOut including pack detail and quota."""
    from app.auth.schemas import PackDetail, QuotaInfo

    pack_data = PACK_CATALOG.get(user.pack, PACK_CATALOG["FREE"])
    pack_detail = PackDetail(**pack_data)

    quota = None
    if user.pack == "FREE":
        limits = PACK_LIMITS["FREE"]
        day_limit = limits["requests_per_day"]
        month_limit = limits["requests_per_month"]
        today = datetime.now(ALGIERS_TZ).date()
        next_reset = (today.replace(day=today.day + 1) if today.day < 28
                      else today.replace(day=1, month=today.month % 12 + 1))
        quota = QuotaInfo(
            requests_today=user.requests_today or 0,
            requests_month=user.requests_month or 0,
            limit_day=day_limit,
            limit_month=month_limit,
            remaining_today=max(0, day_limit - (user.requests_today or 0)),
            remaining_month=max(0, month_limit - (user.requests_month or 0)),
            reset_date=str(today),
        )

    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name or "",
        role=user.role,
        pack=user.pack,
        is_active=user.is_active,
        is_approved=user.is_approved,
        organisation=user.organisation,
        phone=user.phone,
        signup_message=user.signup_message,
        created_at=user.created_at,
        updated_at=user.updated_at,
        pack_detail=pack_detail,
        quota=quota,
    )


# ── Login ──────────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token, summary="Se connecter")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authentification OAuth2 — retourne un JWT Bearer token."""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte en attente de validation par un administrateur",
        )

    return Token(
        access_token=create_user_token(user.email),
        pack=user.pack,
        is_approved=user.is_approved,
    )


# ── Me ─────────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Mon profil",
    description="Retourne le profil complet de l'utilisateur connecté avec le détail du pack et le quota restant.",
)
async def get_me(current_user: User = Depends(get_current_user)):
    """Profil utilisateur enrichi avec pack info et quota."""
    return _build_user_out(current_user)


# ── Update profile ─────────────────────────────────────────────────────────

@router.patch(
    "/me",
    response_model=UserOut,
    summary="Modifier mon profil",
    description="Modifier ses informations personnelles (nom, téléphone, organisation).",
)
async def update_my_profile(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """L'utilisateur met à jour son propre profil."""
    changed = False
    if data.full_name is not None:
        current_user.full_name = data.full_name
        changed = True
    if data.phone is not None:
        current_user.phone = data.phone
        changed = True
    if data.organisation is not None:
        current_user.organisation = data.organisation
        changed = True

    if not changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun champ à modifier fourni.",
        )

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return _build_user_out(current_user)


# ── Change password ────────────────────────────────────────────────────────

@router.post(
    "/me/password",
    summary="Changer mon mot de passe",
    description="Changer son mot de passe en fournissant l'ancien et le nouveau.",
)
async def change_my_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Changement de mot de passe par l'utilisateur."""
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect.",
        )

    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le nouveau mot de passe doit contenir au moins 8 caractères.",
        )

    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le nouveau mot de passe doit être différent de l'ancien.",
        )

    current_user.hashed_password = get_password_hash(data.new_password)
    db.add(current_user)
    await db.commit()

    return {"message": "Mot de passe modifié avec succès."}


# ── My statistics ──────────────────────────────────────────────────────────

@router.get(
    "/me/stats",
    response_model=UserStatsOut,
    summary="Mes statistiques",
    description="Voir ses statistiques d'utilisation : quotas, fonctionnalités accessibles, ancienneté.",
)
async def get_my_stats(current_user: User = Depends(get_current_user)):
    """Statistiques détaillées de l'utilisateur connecté."""
    pack = current_user.pack or "FREE"
    limits = PACK_LIMITS.get(pack, PACK_LIMITS["FREE"])
    day_limit = limits["requests_per_day"]
    month_limit = limits["requests_per_month"]

    pack_data = PACK_CATALOG.get(pack, PACK_CATALOG["FREE"])

    # Features available for this pack
    available = [feat for feat, packs in PACK_FEATURES.items() if pack in packs]

    now = datetime.now(ALGIERS_TZ)
    age_days = (now - current_user.created_at.replace(tzinfo=ALGIERS_TZ)).days

    return UserStatsOut(
        email=current_user.email,
        full_name=current_user.full_name or "",
        pack=pack,
        pack_name=pack_data["name"],
        organisation=current_user.organisation,
        requests_today=current_user.requests_today or 0,
        requests_month=current_user.requests_month or 0,
        limit_day=day_limit,
        limit_month=month_limit,
        remaining_today=max(0, day_limit - (current_user.requests_today or 0)) if day_limit else None,
        remaining_month=max(0, month_limit - (current_user.requests_month or 0)) if month_limit else None,
        is_active=current_user.is_active,
        is_approved=current_user.is_approved,
        account_created=current_user.created_at,
        account_age_days=age_days,
        available_features=available,
    )


# ── My pack detail ─────────────────────────────────────────────────────────

@router.get(
    "/me/pack",
    summary="Détail de mon pack",
    description="Voir le détail complet de son pack actuel (fonctionnalités, limites, cible).",
)
async def get_my_pack(current_user: User = Depends(get_current_user)):
    """Détail du pack de l'utilisateur connecté."""
    pack = current_user.pack or "FREE"
    pack_data = PACK_CATALOG.get(pack, PACK_CATALOG["FREE"])
    return {
        "current_pack": pack,
        "detail": pack_data,
        "all_packs": list(PACK_CATALOG.keys()),
        "upgrade_message": "Pour changer de pack, contactez un administrateur."
        if pack == "FREE" else None,
    }


# ── Delete my account ─────────────────────────────────────────────────────

@router.post(
    "/me/delete",
    summary="Supprimer mon compte",
    description=(
        "Supprimer définitivement son compte. "
        "Vous devez confirmer avec votre mot de passe et votre email."
    ),
)
async def delete_my_account(
    data: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Suppression définitive du compte par l'utilisateur."""
    if data.confirm_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'email de confirmation ne correspond pas.",
        )

    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe incorrect.",
        )

    if current_user.role == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un administrateur ne peut pas supprimer son propre compte.",
        )

    await db.delete(current_user)
    await db.commit()

    return {
        "message": "Votre compte a été supprimé définitivement.",
        "email": current_user.email,
    }


# ── Public signup (pending approval) ──────────────────────────────────────

@router.post(
    "/signup",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Demander un accès",
    description=(
        "Inscription publique. Le compte est créé **en attente de validation** par un administrateur. "
        "Aucun mot de passe n'est requis : il sera généré automatiquement et communiqué après approbation."
    ),
)
async def public_signup(
    user_data: UserPublicSignup,
    db: AsyncSession = Depends(get_db),
):
    """Inscription publique — compte inactif jusqu'à approbation admin."""
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà enregistré",
        )

    # Validate pack
    valid_packs = [p.value for p in PackType]
    pack = user_data.pack.upper()
    if pack not in valid_packs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pack invalide. Valeurs acceptées : {', '.join(valid_packs)}",
        )

    # No password at signup — use a random placeholder (unusable until approval)
    placeholder_hash = get_password_hash(_secrets.token_urlsafe(32))

    new_user = User(
        email=user_data.email,
        hashed_password=placeholder_hash,
        full_name=user_data.full_name,
        role="LECTEUR",
        pack=pack,
        is_active=True,
        is_approved=False,  # Pending admin approval
        organisation=user_data.organisation,
        phone=user_data.phone,
        signup_message=user_data.message,
    )
    db.add(new_user)
    await db.commit()

    return {
        "message": "Demande d'accès enregistrée. Un administrateur examinera votre demande. "
                   "Votre mot de passe vous sera communiqué par email après validation.",
        "email": user_data.email,
        "full_name": user_data.full_name,
        "pack_requested": pack,
        "status": "pending_approval",
    }

