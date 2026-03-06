"""Admin routes: user management, pack assignment, pack catalog."""
import secrets as _secrets
import string
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.auth.models import User, PackType, UserRole
from app.auth.schemas import UserOut, UserListOut, UserCreate, UserUpdate, ApproveRequest
from app.core.security import get_current_admin, get_password_hash
from app.core.packs import PACK_CATALOG, get_pack_info, get_rate_limit
from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["Administration"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_user_out(user: User) -> UserOut:
    """Build UserOut with pack detail and quota."""
    from app.auth.schemas import PackDetail, QuotaInfo
    from app.core.packs import PACK_LIMITS
    from zoneinfo import ZoneInfo
    ALGIERS_TZ = ZoneInfo("Africa/Algiers")

    pack_data = PACK_CATALOG.get(user.pack, PACK_CATALOG["FREE"])
    pack_detail = PackDetail(**pack_data)

    quota = None
    if user.pack == "FREE":
        limits = PACK_LIMITS["FREE"]
        day_limit = limits["requests_per_day"]
        month_limit = limits["requests_per_month"]
        today = datetime.now(ALGIERS_TZ).date()
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


# ══════════════════════════════════════════════════════════════════════════
#  PACK CATALOG (public-ish — readable by any admin)
# ══════════════════════════════════════════════════════════════════════════

@router.get(
    "/packs",
    summary="Catalogue des packs",
    description="Liste tous les packs disponibles avec leurs fonctionnalités et limites.",
    responses={
        200: {"description": "Catalogue complet", "content": {"application/json": {"example": {
            "packs": [
                {"slug": "FREE", "name": "Free", "target": "Développeurs & Tests"},
                {"slug": "PRO", "name": "Pro", "target": "Pharmacies & Grossistes"},
                {"slug": "INSTITUTIONNEL", "name": "Institutionnel", "target": "Établissements de santé"},
                {"slug": "DEVELOPPEUR", "name": "Développeur", "target": "Intégrateurs & Partenaires"},
            ],
            "total": 4,
        }}}},
    },
)
async def list_packs(_: User = Depends(get_current_admin)):
    """Catalogue complet des packs."""
    return {
        "packs": list(PACK_CATALOG.values()),
        "total": len(PACK_CATALOG),
    }


@router.get(
    "/packs/{pack_slug}",
    summary="Détail d'un pack",
    description="Retourne le détail complet d'un pack (fonctionnalités, limites, cible).",
    responses={
        404: {"description": "Pack introuvable", "content": {"application/json": {"example": {"detail": "Pack 'GOLD' introuvable. Valeurs : FREE, PRO, INSTITUTIONNEL, DEVELOPPEUR"}}}},
    },
)
async def get_pack_detail(
    pack_slug: str,
    _: User = Depends(get_current_admin),
):
    """Détail d'un pack par slug."""
    slug = pack_slug.upper()
    if slug not in PACK_CATALOG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pack '{pack_slug}' introuvable. Valeurs : {', '.join(PACK_CATALOG.keys())}",
        )
    return PACK_CATALOG[slug]


# ══════════════════════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════

@router.get(
    "/users",
    response_model=dict,
    summary="Lister les utilisateurs",
    description="Liste paginée de tous les utilisateurs avec filtre par statut et pack.",
    responses={
        200: {"description": "Liste paginée", "content": {"application/json": {"example": {
            "items": [{"id": 5, "email": "pharmacie.benali@email.dz", "full_name": "Dr. Benali Mehdi", "role": "LECTEUR", "pack": "PRO", "is_active": True, "is_approved": True, "created_at": "2026-01-15T08:30:00"}],
            "total": 28, "page": 1, "page_size": 50, "total_pages": 1, "pending_approval": 3,
        }}}},
    },
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    pack: Optional[str] = Query(None, description="Filtrer par pack"),
    is_approved: Optional[bool] = Query(None, description="Filtrer par statut d'approbation"),
    is_active: Optional[bool] = Query(None, description="Filtrer par statut actif"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Liste paginée des utilisateurs."""
    query = select(User)
    count_query = select(func.count(User.id))

    if pack:
        query = query.where(User.pack == pack.upper())
        count_query = count_query.where(User.pack == pack.upper())
    if is_approved is not None:
        query = query.where(User.is_approved == is_approved)
        count_query = count_query.where(User.is_approved == is_approved)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    import math
    return {
        "items": [UserListOut.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "pending_approval": sum(1 for u in users if not u.is_approved),
    }


@router.get(
    "/users/pending",
    summary="Utilisateurs en attente d'approbation",
    description="Liste des inscriptions publiques en attente de validation.",
    responses={
        200: {"description": "Utilisateurs en attente", "content": {"application/json": {"example": {
            "pending": [{"id": 12, "email": "contact@clinique-alger.dz", "full_name": "Dr. Amira Khelifi", "pack": "FREE", "is_approved": False, "created_at": "2026-03-05T14:20:00"}],
            "total": 3,
        }}}},
    },
)
async def list_pending_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Comptes (is_approved=False) en attente."""
    result = await db.execute(
        select(User).where(User.is_approved == False).order_by(User.created_at.asc())
    )
    users = result.scalars().all()
    return {
        "pending": [UserListOut.model_validate(u) for u in users],
        "total": len(users),
    }


@router.get(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Détail d'un utilisateur",
    responses={
        404: {"description": "Utilisateur introuvable", "content": {"application/json": {"example": {"detail": "Utilisateur introuvable"}}}},
    },
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Détail complet d'un utilisateur."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    return _build_user_out(user)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un utilisateur (admin)",
    description="L'admin crée directement un utilisateur approuvé avec le pack de son choix.",
    responses={
        201: {"description": "Utilisateur créé"},
        400: {"description": "Email déjà enregistré ou pack invalide", "content": {"application/json": {"example": {"detail": "Email déjà enregistré"}}}},
    },
)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Créer un utilisateur (approuvé immédiatement)."""
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email déjà enregistré")

    pack = user_data.pack.upper() if user_data.pack else "FREE"
    if pack not in [p.value for p in PackType]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Pack invalide : {pack}")

    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role.upper() if user_data.role else "LECTEUR",
        pack=pack,
        is_active=True,
        is_approved=True,
        organisation=user_data.organisation,
        phone=user_data.phone,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return _build_user_out(new_user)


@router.patch(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Modifier un utilisateur",
    description="Mettre à jour rôle, pack, statut actif/approuvé, organisation.",
    responses={
        200: {"description": "Utilisateur mis à jour"},
        404: {"description": "Utilisateur introuvable", "content": {"application/json": {"example": {"detail": "Utilisateur introuvable"}}}},
        400: {"description": "Rôle ou pack invalide", "content": {"application/json": {"example": {"detail": "Pack invalide : GOLD"}}}},
    },
)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Mise à jour partielle d'un utilisateur."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.password is not None:
        user.hashed_password = get_password_hash(user_data.password)
    if user_data.role is not None:
        role = user_data.role.upper()
        if role not in [r.value for r in UserRole]:
            raise HTTPException(status_code=400, detail=f"Rôle invalide : {role}")
        user.role = role
    if user_data.pack is not None:
        pack = user_data.pack.upper()
        if pack not in [p.value for p in PackType]:
            raise HTTPException(status_code=400, detail=f"Pack invalide : {pack}")
        user.pack = pack
        # Reset quotas when pack changes
        user.requests_today = 0
        user.requests_month = 0
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.is_approved is not None:
        user.is_approved = user_data.is_approved
    if user_data.organisation is not None:
        user.organisation = user_data.organisation
    if user_data.phone is not None:
        user.phone = user_data.phone

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _build_user_out(user)


@router.post(
    "/users/{user_id}/approve",
    response_model=dict,
    summary="Approuver un utilisateur",
    description=(
        "Approuver un compte en attente. Un mot de passe est généré automatiquement "
        "(ou défini par l'admin) puis renvoyé dans la réponse pour communication à l'utilisateur."
    ),
    responses={
        200: {"description": "Utilisateur approuvé", "content": {"application/json": {"example": {
            "message": "Utilisateur contact@clinique-alger.dz approuvé avec le pack PRO.",
            "user_id": 12, "email": "contact@clinique-alger.dz",
            "full_name": "Dr. Amira Khelifi", "pack": "PRO",
            "generated_password": "xK9#mQ2$vL7&pR4!",
            "email_sent": True,
            "note": "Les identifiants ont été envoyés par email.",
        }}}},
        400: {"description": "Déjà approuvé", "content": {"application/json": {"example": {"detail": "Utilisateur déjà approuvé"}}}},
        404: {"description": "Introuvable", "content": {"application/json": {"example": {"detail": "Utilisateur introuvable"}}}},
    },
)
async def approve_user(
    user_id: int,
    body: ApproveRequest = ApproveRequest(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Approuver une inscription en attente et générer/attribuer un mot de passe."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    if user.is_approved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Utilisateur déjà approuvé")

    pack_val = (body.pack or "FREE").upper()
    if pack_val not in [p.value for p in PackType]:
        raise HTTPException(status_code=400, detail=f"Pack invalide : {pack_val}")

    # Password: admin-defined or auto-generated
    if body.password:
        plain_password = body.password
    else:
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
        plain_password = "".join(_secrets.choice(alphabet) for _ in range(16))

    user.hashed_password = get_password_hash(plain_password)
    user.is_approved = True
    user.pack = pack_val
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send approval email with credentials
    from app.core.email import send_account_approved
    email_sent = await send_account_approved(
        to_email=user.email,
        full_name=user.full_name or user.email,
        pack=pack_val,
        password=plain_password,
    )

    return {
        "message": f"Utilisateur {user.email} approuvé avec le pack {pack_val}.",
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "pack": pack_val,
        "generated_password": plain_password,
        "email_sent": email_sent,
        "note": "Les identifiants ont été envoyés par email." if email_sent else "Communiquez ce mot de passe à l'utilisateur manuellement.",
    }


@router.post(
    "/users/{user_id}/pack",
    response_model=UserOut,
    summary="Changer le pack",
    description="Changer le pack d'abonnement d'un utilisateur. Réinitialise les compteurs FREE.",
    responses={
        200: {"description": "Pack modifié"},
        400: {"description": "Pack invalide", "content": {"application/json": {"example": {"detail": "Pack invalide. Valeurs acceptées : FREE, PRO, INSTITUTIONNEL, DEVELOPPEUR"}}}},
        404: {"description": "Utilisateur introuvable", "content": {"application/json": {"example": {"detail": "Utilisateur introuvable"}}}},
    },
)
async def change_pack(
    user_id: int,
    pack: str = Query(..., description="Nouveau pack : FREE | PRO | INSTITUTIONNEL | DEVELOPPEUR"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Changer le pack d'un utilisateur."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    pack_val = pack.upper()
    if pack_val not in [p.value for p in PackType]:
        raise HTTPException(
            status_code=400,
            detail=f"Pack invalide. Valeurs acceptées : {', '.join([p.value for p in PackType])}",
        )

    old_pack = user.pack
    user.pack = pack_val
    user.requests_today = 0
    user.requests_month = 0
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Notify user of pack change
    from app.core.email import send_pack_changed
    await send_pack_changed(
        to_email=user.email,
        full_name=user.full_name or user.email,
        old_pack=str(old_pack),
        new_pack=pack_val,
    )

    return _build_user_out(user)


@router.delete(
    "/users/{user_id}",
    summary="Désactiver un utilisateur",
    description="Désactive le compte (soft delete — is_active=False).",
    responses={
        200: {"description": "Utilisateur désactivé", "content": {"application/json": {"example": {"message": "Utilisateur pharmacie.benali@email.dz désactivé", "user_id": 5}}}},
        400: {"description": "Auto-désactivation interdite", "content": {"application/json": {"example": {"detail": "Vous ne pouvez pas désactiver votre propre compte"}}}},
        404: {"description": "Utilisateur introuvable", "content": {"application/json": {"example": {"detail": "Utilisateur introuvable"}}}},
    },
)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Désactiver un utilisateur (soft delete)."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    user.is_active = False
    db.add(user)
    await db.commit()

    # Notify user of account deactivation
    from app.core.email import send_account_rejected
    await send_account_rejected(
        to_email=user.email,
        full_name=user.full_name or user.email,
        reason="Votre compte a été désactivé par un administrateur.",
    )

    return {"message": f"Utilisateur {user.email} désactivé", "user_id": user_id}


# ══════════════════════════════════════════════════════════════════════════
#  STATS ADMIN
# ══════════════════════════════════════════════════════════════════════════

@router.get(
    "/stats",
    summary="Statistiques admin",
    description="Résumé des utilisateurs par pack, statut et activité.",
    responses={
        200: {"description": "Tableau de bord admin", "content": {"application/json": {"example": {
            "total_users": 28, "approved": 25, "pending_approval": 3,
            "active": 26, "inactive": 2,
            "by_pack": {"FREE": 10, "PRO": 12, "INSTITUTIONNEL": 4, "DEVELOPPEUR": 2},
        }}}},
    },
)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Tableau de bord admin."""
    result = await db.execute(select(User))
    users = result.scalars().all()

    by_pack = {}
    for p in PackType:
        by_pack[p.value] = sum(1 for u in users if u.pack == p.value)

    return {
        "total_users": len(users),
        "approved": sum(1 for u in users if u.is_approved),
        "pending_approval": sum(1 for u in users if not u.is_approved),
        "active": sum(1 for u in users if u.is_active),
        "inactive": sum(1 for u in users if not u.is_active),
        "by_pack": by_pack,
    }


# ══════════════════════════════════════════════════════════════════════════
#  API KEYS MANAGEMENT (Admin)
# ══════════════════════════════════════════════════════════════════════════

@router.get(
    "/api-keys",
    summary="Lister toutes les clés API",
    description="Vue admin de toutes les clés API avec informations utilisateur, pack et usage.",
    responses={
        200: {"description": "Liste paginée des clés API", "content": {"application/json": {"example": {
            "api_keys": [{
                "id": 1, "user_id": 5, "user_email": "pharmacie.benali@email.dz",
                "user_pack": "PRO", "name": "Mon App Mobile",
                "key_prefix": "npp_a3f7...****", "is_active": True,
                "created_at": "2026-03-01T10:00:00",
                "last_used_at": "2026-03-06T14:22:00",
                "last_used_ip": "41.111.22.33", "requests_count": 1523,
            }],
            "total": 15, "page": 1, "page_size": 50,
        }}}},
    },
)
async def admin_list_api_keys(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None, description="Filtrer par utilisateur"),
    is_active: Optional[bool] = Query(None, description="Filtrer par statut actif"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Liste paginée de toutes les clés API."""
    from app.models.api_key import ApiKey

    query = select(ApiKey).order_by(ApiKey.created_at.desc())
    count_query = select(func.count()).select_from(ApiKey)

    if user_id is not None:
        query = query.where(ApiKey.user_id == user_id)
        count_query = count_query.where(ApiKey.user_id == user_id)
    if is_active is not None:
        query = query.where(ApiKey.is_active == is_active)
        count_query = count_query.where(ApiKey.is_active == is_active)

    total = await db.scalar(count_query)
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    keys = result.scalars().all()

    return {
        "api_keys": [
            {
                "id": k.id,
                "user_id": k.user_id,
                "user_email": k.user.email if k.user else None,
                "user_pack": k.user.pack if k.user else None,
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
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/api-keys/{key_id}",
    summary="Détail d'une clé API",
    description="Voir le détail complet d'une clé API.",
    responses={
        200: {"description": "Détail de la clé", "content": {"application/json": {"example": {
            "id": 1, "user_id": 5, "user_email": "pharmacie.benali@email.dz",
            "user_pack": "PRO", "user_full_name": "Dr. Benali Mehdi",
            "name": "Mon App Mobile", "key_prefix": "npp_a3f7...****",
            "is_active": True, "created_at": "2026-03-01T10:00:00",
            "last_used_at": "2026-03-06T14:22:00",
            "last_used_ip": "41.111.22.33", "requests_count": 1523,
        }}}},
        404: {"description": "Clé introuvable", "content": {"application/json": {"example": {"detail": "Clé API introuvable."}}}},
    },
)
async def admin_get_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Détail d'une clé API."""
    from app.models.api_key import ApiKey

    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clé API introuvable.")

    return {
        "id": api_key.id,
        "user_id": api_key.user_id,
        "user_email": api_key.user.email if api_key.user else None,
        "user_pack": api_key.user.pack if api_key.user else None,
        "user_full_name": api_key.user.full_name if api_key.user else None,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "is_active": api_key.is_active,
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
        "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        "last_used_ip": api_key.last_used_ip,
        "requests_count": api_key.requests_count or 0,
    }


@router.patch(
    "/api-keys/{key_id}",
    summary="Activer/désactiver une clé API",
    description="L'administrateur peut activer ou désactiver une clé API.",
    responses={
        200: {"description": "Clé modifiée", "content": {"application/json": {"example": {"message": "Clé API désactivée.", "id": 1, "is_active": False}}}},
        404: {"description": "Clé introuvable", "content": {"application/json": {"example": {"detail": "Clé API introuvable."}}}},
    },
)
async def admin_toggle_api_key(
    key_id: int,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Active ou désactive une clé API."""
    from app.models.api_key import ApiKey

    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clé API introuvable.")

    api_key.is_active = is_active
    db.add(api_key)
    await db.commit()

    action = "activée" if is_active else "désactivée"
    return {"message": f"Clé API {action}.", "id": key_id, "is_active": is_active}


@router.delete(
    "/api-keys/{key_id}",
    summary="Supprimer une clé API",
    description="Supprime définitivement une clé API.",
    responses={
        200: {"description": "Clé supprimée", "content": {"application/json": {"example": {"message": "Clé API supprimée définitivement.", "id": 1}}}},
        404: {"description": "Clé introuvable", "content": {"application/json": {"example": {"detail": "Clé API introuvable."}}}},
    },
)
async def admin_delete_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Supprime une clé API."""
    from app.models.api_key import ApiKey

    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clé API introuvable.")

    await db.delete(api_key)
    await db.commit()

    return {"message": "Clé API supprimée définitivement.", "id": key_id}


@router.get(
    "/users/{user_id}/api-keys",
    summary="Clés API d'un utilisateur",
    description="Voir toutes les clés API d'un utilisateur spécifique.",
    responses={
        200: {"description": "Clés API de l'utilisateur", "content": {"application/json": {"example": {
            "user_id": 5, "user_email": "pharmacie.benali@email.dz", "user_pack": "PRO",
            "api_keys": [{"id": 1, "name": "Mon App Mobile", "key_prefix": "npp_a3f7...****", "is_active": True, "created_at": "2026-03-01T10:00:00", "last_used_at": "2026-03-06T14:22:00", "requests_count": 1523}],
            "total": 1,
        }}}},
        404: {"description": "Utilisateur introuvable", "content": {"application/json": {"example": {"detail": "Utilisateur introuvable."}}}},
    },
)
async def admin_user_api_keys(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Clés API d'un utilisateur."""
    from app.models.api_key import ApiKey

    # Vérifier que l'utilisateur existe
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable.")

    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    return {
        "user_id": user_id,
        "user_email": user.email,
        "user_pack": user.pack,
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
    }


# ══════════════════════════════════════════════════════════════════════════
#  EMAIL MANAGEMENT (Admin)
# ══════════════════════════════════════════════════════════════════════════

@router.get(
    "/email/status",
    summary="Statut du service email",
    description="Vérifie la configuration Microsoft 365 Graph API pour l'envoi d'emails.",
    tags=["Administration", "Email"],
    responses={
        200: {"description": "Statut de la configuration email", "content": {"application/json": {"example": {
            "enabled": True, "configured": True, "provider": "Microsoft Graph API",
            "mail_from": "noreply@forge-solutions.tech",
            "mail_from_name": "NPP API",
            "admin_notification_email": "admin@forge-solutions.tech",
            "tenant_id_set": True, "client_id_set": True, "client_secret_set": True,
            "templates": ["signup_confirmation", "admin_new_signup", "account_approved", "account_rejected", "password_changed", "password_reset", "api_key_created", "pack_changed", "test_email"],
        }}}},
    },
)
async def email_status(_: User = Depends(get_current_admin)):
    """État de la configuration email Microsoft 365."""
    from app.core.config import settings

    configured = all([
        settings.MICROSOFT_TENANT_ID,
        settings.MICROSOFT_CLIENT_ID,
        settings.MICROSOFT_CLIENT_SECRET,
        settings.MAIL_FROM,
    ])

    return {
        "enabled": settings.MAIL_ENABLED,
        "configured": configured,
        "provider": "Microsoft Graph API",
        "mail_from": settings.MAIL_FROM or "(non configuré)",
        "mail_from_name": settings.MAIL_FROM_NAME,
        "admin_notification_email": settings.ADMIN_NOTIFICATION_EMAIL or "(non configuré)",
        "tenant_id_set": bool(settings.MICROSOFT_TENANT_ID),
        "client_id_set": bool(settings.MICROSOFT_CLIENT_ID),
        "client_secret_set": bool(settings.MICROSOFT_CLIENT_SECRET),
        "templates": [
            "signup_confirmation",
            "admin_new_signup",
            "account_approved",
            "account_rejected",
            "password_changed",
            "password_reset",
            "api_key_created",
            "pack_changed",
            "test_email",
        ],
    }


@router.post(
    "/email/test",
    summary="Envoyer un email de test",
    description="Envoie un email de test pour vérifier que la configuration M365 fonctionne.",
    tags=["Administration", "Email"],
    responses={
        200: {"description": "Résultat de l'envoi", "content": {"application/json": {"examples": {
            "success": {"value": {"message": "Email de test envoyé à admin@forge-solutions.tech", "success": True}},
            "failure": {"value": {"message": "Échec de l'envoi. Vérifiez la configuration M365 et les logs.", "success": False, "hint": "Assurez-vous que MAIL_ENABLED=true et que les credentials M365 sont corrects."}},
        }}}},
    },
)
async def send_test(
    to_email: str = Query(..., description="Adresse email du destinataire"),
    _: User = Depends(get_current_admin),
):
    """Envoyer un email de test via Microsoft Graph API."""
    from app.core.email import send_test_email

    success = await send_test_email(to_email=to_email)

    if success:
        return {"message": f"Email de test envoyé à {to_email}", "success": True}
    else:
        return {
            "message": "Échec de l'envoi. Vérifiez la configuration M365 et les logs.",
            "success": False,
            "hint": "Assurez-vous que MAIL_ENABLED=true et que les credentials M365 sont corrects.",
        }


@router.post(
    "/email/send",
    summary="Envoyer un email personnalisé",
    description="Envoie un email personnalisé à un utilisateur (corps HTML libre).",
    tags=["Administration", "Email"],
    responses={
        200: {"description": "Résultat de l'envoi", "content": {"application/json": {"example": {"success": True, "to": "pharmacie.benali@email.dz", "subject": "Information importante"}}}},
    },
)
async def send_custom_email(
    to_email: str = Query(..., description="Adresse email du destinataire"),
    subject: str = Query(..., description="Sujet de l'email"),
    body_html: str = Query(..., description="Corps HTML de l'email"),
    _: User = Depends(get_current_admin),
):
    """Envoyer un email personnalisé."""
    from app.core.email import send_email

    success = await send_email(
        to_email=to_email,
        subject=subject,
        html_body=body_html,
    )

    return {"success": success, "to": to_email, "subject": subject}


@router.post(
    "/users/{user_id}/reset-password",
    summary="Réinitialiser le mot de passe",
    description=(
        "Réinitialise le mot de passe d'un utilisateur et lui envoie "
        "les nouveaux identifiants par email."
    ),
    tags=["Administration", "Email"],
    responses={
        200: {"description": "Mot de passe réinitialisé", "content": {"application/json": {"example": {
            "message": "Mot de passe réinitialisé pour pharmacie.benali@email.dz",
            "user_id": 5, "email": "pharmacie.benali@email.dz",
            "generated_password": "xK9#mQ2$vL7&pR4!", "email_sent": True,
        }}}},
        404: {"description": "Utilisateur introuvable", "content": {"application/json": {"example": {"detail": "Utilisateur introuvable"}}}},
    },
)
async def admin_reset_password(
    user_id: int,
    new_password: Optional[str] = Query(None, description="Mot de passe (auto-généré si vide)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Réinitialiser le mot de passe d'un utilisateur et notifier par email."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    # Generate password if not provided
    if new_password:
        plain_password = new_password
    else:
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
        plain_password = "".join(_secrets.choice(alphabet) for _ in range(16))

    user.hashed_password = get_password_hash(plain_password)
    db.add(user)
    await db.commit()

    # Send reset email
    from app.core.email import send_password_reset
    email_sent = await send_password_reset(
        to_email=user.email,
        full_name=user.full_name or user.email,
        new_password=plain_password,
    )

    return {
        "message": f"Mot de passe réinitialisé pour {user.email}",
        "user_id": user.id,
        "email": user.email,
        "generated_password": plain_password,
        "email_sent": email_sent,
    }
