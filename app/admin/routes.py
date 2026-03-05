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

    return {
        "message": f"Utilisateur {user.email} approuvé avec le pack {pack_val}.",
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "pack": pack_val,
        "generated_password": plain_password,
        "note": "Communiquez ce mot de passe à l'utilisateur par email.",
    }


@router.post(
    "/users/{user_id}/pack",
    response_model=UserOut,
    summary="Changer le pack",
    description="Changer le pack d'abonnement d'un utilisateur. Réinitialise les compteurs FREE.",
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

    user.pack = pack_val
    user.requests_today = 0
    user.requests_month = 0
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _build_user_out(user)


@router.delete(
    "/users/{user_id}",
    summary="Désactiver un utilisateur",
    description="Désactive le compte (soft delete — is_active=False).",
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
    return {"message": f"Utilisateur {user.email} désactivé", "user_id": user_id}


# ══════════════════════════════════════════════════════════════════════════
#  STATS ADMIN
# ══════════════════════════════════════════════════════════════════════════

@router.get(
    "/stats",
    summary="Statistiques admin",
    description="Résumé des utilisateurs par pack, statut et activité.",
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
