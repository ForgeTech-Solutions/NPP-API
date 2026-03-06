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

@router.post(
    "/login",
    response_model=Token,
    summary="Se connecter",
    description="Authentification OAuth2 password flow. Retourne un JWT Bearer token valide 30 minutes.",
    responses={
        200: {
            "description": "Connexion réussie",
            "content": {"application/json": {"example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkBub21lbmNsYXR1cmUuZHoiLCJleHAiOjE3NDEyNzI4MDB9.abc123",
                "token_type": "bearer",
                "pack": "DEVELOPPEUR",
                "is_approved": True,
            }}},
        },
        401: {"description": "Email ou mot de passe incorrect", "content": {"application/json": {"example": {"detail": "Email ou mot de passe incorrect"}}}},
        403: {"description": "Compte désactivé ou en attente", "content": {"application/json": {"example": {"detail": "Compte en attente de validation par un administrateur"}}}},
    },
)
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
    responses={
        200: {"description": "Profil utilisateur", "content": {"application/json": {"example": {
            "id": 5, "email": "pharmacie.benali@email.dz", "full_name": "Dr. Benali Mehdi",
            "phone": "+213 555 123 456", "organisation": "Pharmacie Benali - Alger",
            "is_active": True, "is_approved": True, "pack": "PRO",
            "role": "user", "requests_today": 42, "requests_month": 890,
            "created_at": "2026-01-15T08:30:00",
            "quota_info": {"day_limit": None, "month_limit": None, "remaining_today": None, "remaining_month": None},
            "pack_detail": {"slug": "PRO", "name": "Pro", "target": "Pharmacies & Grossistes"},
        }}}},
        401: {"description": "Non authentifié", "content": {"application/json": {"example": {"detail": "Not authenticated"}}}},
    },
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
    responses={
        200: {"description": "Profil mis à jour"},
        400: {"description": "Aucun champ fourni", "content": {"application/json": {"example": {"detail": "Aucun champ à modifier fourni."}}}},
    },
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
    description="Changer son mot de passe en fournissant l'ancien et le nouveau. Le nouveau doit faire au moins 8 caractères.",
    responses={
        200: {"description": "Mot de passe modifié", "content": {"application/json": {"example": {"message": "Mot de passe modifié avec succès."}}}},
        400: {"description": "Erreur de validation", "content": {"application/json": {"examples": {
            "incorrect": {"value": {"detail": "Mot de passe actuel incorrect."}},
            "trop_court": {"value": {"detail": "Le nouveau mot de passe doit contenir au moins 8 caractères."}},
            "identique": {"value": {"detail": "Le nouveau mot de passe doit être différent de l'ancien."}},
        }}}},
    },
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

    # Send password change confirmation email
    from app.core.email import send_password_changed
    await send_password_changed(
        to_email=current_user.email,
        full_name=current_user.full_name or current_user.email,
    )

    return {"message": "Mot de passe modifié avec succès."}


# ── My statistics ──────────────────────────────────────────────────────────

@router.get(
    "/me/stats",
    response_model=UserStatsOut,
    summary="Mes statistiques",
    description="Voir ses statistiques d'utilisation : quotas, fonctionnalités accessibles, ancienneté.",
    responses={
        200: {"description": "Statistiques utilisateur", "content": {"application/json": {"example": {
            "email": "pharmacie.benali@email.dz", "full_name": "Dr. Benali Mehdi",
            "pack": "PRO", "pack_name": "Pro", "organisation": "Pharmacie Benali - Alger",
            "requests_today": 42, "requests_month": 890,
            "limit_day": None, "limit_month": None,
            "remaining_today": None, "remaining_month": None,
            "is_active": True, "is_approved": True,
            "account_created": "2026-01-15T08:30:00",
            "account_age_days": 50,
            "available_features": ["search", "export_csv", "dci_group", "statistics", "dashboard"],
        }}}},
    },
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
    responses={
        200: {"description": "Détail du pack", "content": {"application/json": {"example": {
            "current_pack": "PRO",
            "detail": {
                "slug": "PRO", "name": "Pro", "target": "Pharmacies & Grossistes",
                "description": "Officines et grossistes répartiteurs.",
                "features": ["Recherche par DCI, marque ou code AMM", "Export CSV", "Requêtes illimitées"],
                "limitations": [], "rate_limit_day": None, "rate_limit_month": None, "requires_approval": True,
            },
            "all_packs": ["FREE", "PRO", "INSTITUTIONNEL", "DEVELOPPEUR"],
            "upgrade_message": None,
        }}}},
    },
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
    responses={
        200: {"description": "Compte supprimé", "content": {"application/json": {"example": {
            "message": "Votre compte a été supprimé définitivement.",
            "email": "pharmacie.benali@email.dz",
        }}}},
        400: {"description": "Confirmation invalide", "content": {"application/json": {"example": {"detail": "Mot de passe incorrect."}}}},
        403: {"description": "Admin interdit", "content": {"application/json": {"example": {"detail": "Un administrateur ne peut pas supprimer son propre compte."}}}},
    },
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
    responses={
        201: {"description": "Demande enregistrée", "content": {"application/json": {"example": {
            "message": "Demande d'accès enregistrée. Un administrateur examinera votre demande. Votre mot de passe vous sera communiqué par email après validation.",
            "email": "contact@clinique-alger.dz",
            "full_name": "Dr. Amira Khelifi",
            "pack_requested": "INSTITUTIONNEL",
            "status": "pending_approval",
        }}}},
        400: {"description": "Email déjà enregistré ou pack invalide", "content": {"application/json": {"example": {"detail": "Cet email est déjà enregistré"}}}},
    },
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

    # Send confirmation email to user + notification to admin
    from app.core.email import send_signup_confirmation, send_admin_new_signup_notification
    await send_signup_confirmation(
        to_email=user_data.email,
        full_name=user_data.full_name,
        pack=pack,
        organisation=user_data.organisation or "",
    )
    await send_admin_new_signup_notification(
        user_email=user_data.email,
        full_name=user_data.full_name,
        pack=pack,
        organisation=user_data.organisation or "",
        message=user_data.message or "",
    )

    return {
        "message": "Demande d'accès enregistrée. Un administrateur examinera votre demande. "
                   "Votre mot de passe vous sera communiqué par email après validation.",
        "email": user_data.email,
        "full_name": user_data.full_name,
        "pack_requested": pack,
        "status": "pending_approval",
    }


# ══════════════════════════════════════════════════════════════════════════
#  API KEYS — Self-service
# ══════════════════════════════════════════════════════════════════════════

@router.get(
    "/me/api-keys",
    summary="Lister mes clés API",
    description="Retourne toutes vos clés API avec leur statut, date de dernière utilisation et compteur.",
    responses={
        200: {"description": "Liste des clés API", "content": {"application/json": {"example": {
            "api_keys": [
                {
                    "id": 1,
                    "name": "Mon App Mobile",
                    "key_prefix": "npp_a3f7...****",
                    "is_active": True,
                    "created_at": "2026-03-01T10:00:00",
                    "last_used_at": "2026-03-06T14:22:00",
                    "last_used_ip": "41.111.22.33",
                    "requests_count": 1523,
                }
            ],
            "total": 1,
            "max_keys": 3,
            "remaining_slots": 2,
        }}}},
    },
)
async def list_my_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Liste des clés API de l'utilisateur connecté."""
    from app.models.api_key import ApiKey
    from app.core.packs import API_KEY_LIMITS

    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    max_keys = API_KEY_LIMITS.get(current_user.pack, 1)

    return {
        "api_keys": [
            {
                "id": k.id,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "is_active": k.is_active,
                "created_at": k.created_at.isoformat() if k.created_at else None,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "last_used_ip": k.last_used_ip,
                "requests_count": k.requests_count or 0,
            }
            for k in keys
        ],
        "total": len(keys),
        "max_keys": max_keys,
        "remaining_slots": max(0, max_keys - len(keys)),
    }


@router.post(
    "/me/api-keys",
    status_code=status.HTTP_201_CREATED,
    summary="Créer une clé API",
    description=(
        "Génère une nouvelle clé API permanente liée à votre compte et votre pack. "
        "**La clé complète n'est affichée qu'une seule fois** — copiez-la immédiatement."
    ),
    responses={
        201: {"description": "Clé API créée", "content": {"application/json": {"example": {
            "message": "Clé API créée. Copiez-la maintenant — elle ne sera plus affichée.",
            "api_key": "npp_a3f7e9b2c4d6f8a1e3b5c7d9f0a2b4c6d8e0f1a3b5c7d9",
            "id": 2,
            "name": "Mon App Mobile",
            "key_prefix": "npp_a3f7...****",
            "pack": "PRO",
            "created_at": "2026-03-06T15:00:00",
        }}}},
        403: {"description": "Limite atteinte", "content": {"application/json": {"example": {
            "detail": {
                "error": "api_key_limit_reached",
                "message": "Limite de 3 clé(s) API atteinte pour le pack PRO.",
                "current_count": 3,
                "max_keys": 3,
                "upgrade_hint": "Contactez un administrateur pour changer de pack.",
            }
        }}}},
    },
)
async def create_my_api_key(
    name: str = "Ma clé API",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crée une clé API pour l'utilisateur connecté."""
    from app.models.api_key import ApiKey, generate_api_key, hash_api_key
    from app.core.packs import API_KEY_LIMITS

    max_keys = API_KEY_LIMITS.get(current_user.pack, 1)

    # Count existing keys
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id)
    )
    existing = result.scalars().all()

    if len(existing) >= max_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "api_key_limit_reached",
                "message": f"Limite de {max_keys} clé(s) API atteinte pour le pack {current_user.pack}.",
                "current_count": len(existing),
                "max_keys": max_keys,
                "upgrade_hint": "Contactez un administrateur pour changer de pack.",
            },
        )

    # Generate
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    key_prefix = ApiKey.mask_key(raw_key)

    api_key = ApiKey(
        user_id=current_user.id,
        name=name.strip()[:100],
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    # Send notification email
    from app.core.email import send_api_key_created
    await send_api_key_created(
        to_email=current_user.email,
        full_name=current_user.full_name or current_user.email,
        key_name=api_key.name,
        key_prefix=key_prefix,
    )

    return {
        "message": "Clé API créée. Copiez-la maintenant — elle ne sera plus affichée.",
        "api_key": raw_key,
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": key_prefix,
        "pack": current_user.pack,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
    }


@router.delete(
    "/me/api-keys/{key_id}",
    summary="Révoquer une clé API",
    description="Supprime définitivement l'une de vos clés API.",
    responses={
        200: {"description": "Clé révoquée", "content": {"application/json": {"example": {"message": "Clé API révoquée avec succès.", "id": 2}}}},
        404: {"description": "Clé introuvable", "content": {"application/json": {"example": {"detail": "Clé API introuvable ou ne vous appartient pas."}}}},
    },
)
async def delete_my_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Révoque (supprime) une clé API de l'utilisateur connecté."""
    from app.models.api_key import ApiKey

    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clé API introuvable ou ne vous appartient pas.",
        )

    await db.delete(api_key)
    await db.commit()

    return {"message": "Clé API révoquée avec succès.", "id": key_id}

