"""Medicaments routes."""
import math
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date
import io

from app.medicaments.schemas import (
    MedicamentOut,
    MedicamentCreate,
    MedicamentUpdate,
    PaginatedResponse,
    MedicamentStatistics,
    DashboardStatistics,
    DCIGroupResponse,
)
from app.medicaments import crud
from app.auth.models import User
from app.core.security import get_current_user, get_current_admin, require_pack, require_any_pack
from app.core.cache import cache
from app.db.session import get_db

# Pack shorthand aliases
_FREE_AND_UP  = require_any_pack()               # FREE / PRO / INSTITUTIONNEL / DEVELOPPEUR
_PRO_AND_UP   = require_pack(["PRO", "INSTITUTIONNEL", "DEVELOPPEUR"])
_INST_AND_UP  = require_pack(["INSTITUTIONNEL", "DEVELOPPEUR"])

router = APIRouter(prefix="/medicaments", tags=["Medicaments"])


@router.get(
    "",
    response_model=PaginatedResponse[MedicamentOut],
    summary="Lister les médicaments",
    description=(
        "Liste paginée avec recherche full-text et 15+ filtres.\n\n"
        "**Pack FREE** : recherche `q`, `dci`, `nom_marque`, `code`, pagination — rate limit 100 req/j.\n\n"
        "**Pack PRO+** : tous les filtres avancés (laboratoire, pays, type, statut, catégorie, dates…)"
    ),
    responses={
        200: {"description": "Liste paginée de médicaments", "content": {"application/json": {"example": {
            "items": [{"id": 1542, "code": "01 A 003", "dci": "CETIRIZINE DICHLORHYDRATE", "nom_marque": "ARTIZ", "forme": "COMPRIME PELLICULE SECABLE", "dosage": "10MG", "conditionnement": "B/10", "laboratoire": "EL KENDI", "pays_laboratoire": "ALGERIE", "type_medicament": "GE", "statut": "F", "categorie": "NOMENCLATURE", "version_nomenclature": "2025-06-30", "created_at": "2026-01-10T09:00:00", "updated_at": "2026-01-10T09:00:00"}],
            "total": 12345, "page": 1, "page_size": 50, "total_pages": 247, "has_next": True, "has_previous": False,
        }}}},
        403: {"description": "Pack insuffisant", "content": {"application/json": {"example": {"detail": "Pack insuffisant. Requis : FREE, PRO, INSTITUTIONNEL ou DEVELOPPEUR."}}}},
    },
)
async def list_medicaments(
    page: int = Query(1, ge=1, description="Numéro de page"),
    page_size: int = Query(50, ge=1, le=200, description="Éléments par page"),
    q: Optional[str] = Query(None, description="Recherche full-text (DCI, nom_marque, code, laboratoire)"),
    dci: Optional[str] = Query(None, description="Filtrer par DCI"),
    nom_marque: Optional[str] = Query(None, description="Filtrer par nom de marque"),
    code: Optional[str] = Query(None, description="Filtrer par code produit"),
    num_enregistrement: Optional[str] = Query(None, description="Filtrer par numéro d'enregistrement"),
    laboratoire: Optional[str] = Query(None, description="Filtrer par laboratoire"),
    pays_laboratoire: Optional[str] = Query(None, description="Filtrer par pays du laboratoire"),
    liste: Optional[str] = Query(None, description="Filtrer par liste (I, II)"),
    type: Optional[str] = Query(None, alias="type", description="Filtrer par type (GE, RE, BIO)"),
    statut: Optional[str] = Query(None, description="Filtrer par statut (F, I)"),
    categorie: Optional[str] = Query(None, description="Filtrer par catégorie (NOMENCLATURE, NON_RENOUVELE, RETRAIT)"),
    date_initial_min: Optional[date] = Query(None, description="Date d'enregistrement initial min"),
    date_initial_max: Optional[date] = Query(None, description="Date d'enregistrement initial max"),
    version: Optional[str] = Query(None, description="Filtrer par version nomenclature"),
    sort_by: str = Query("id", description="Trier par: id, code, dci, nom_marque, laboratoire, pays_laboratoire, type_medicament, categorie, date_enregistrement_initial, created_at"),
    order: str = Query("asc", description="Ordre de tri: asc ou desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_FREE_AND_UP)
):
    """Liste et recherche de médicaments avec pagination, filtres et tri."""
    medicaments, total = await crud.get_medicaments(
        db=db, page=page, page_size=page_size, q=q, dci=dci,
        nom_marque=nom_marque, code=code, num_enregistrement=num_enregistrement,
        laboratoire=laboratoire, pays_laboratoire=pays_laboratoire,
        liste=liste, type_medicament=type, statut=statut, categorie=categorie,
        date_initial_min=date_initial_min, date_initial_max=date_initial_max,
        version=version, sort_by=sort_by, order=order
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return PaginatedResponse(
        items=medicaments,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@router.get(
    "/statistiques",
    response_model=MedicamentStatistics,
    summary="Statistiques des médicaments",
    description="Retourne les statistiques groupées par laboratoire, pays, type, catégorie et statut.",
    responses={
        200: {"description": "Statistiques"},
        403: {"description": "Pack insuffisant (INSTITUTIONNEL+ requis)", "content": {"application/json": {"example": {"detail": "Pack insuffisant. Requis : INSTITUTIONNEL ou DEVELOPPEUR."}}}},
    },
)
async def get_statistics(
    categorie: Optional[str] = Query(None, description="Filtrer par catégorie"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_INST_AND_UP)
):
    """Statistiques avec filtre optionnel par catégorie."""
    cache_key = f"stats:{categorie or 'all'}"
    cached = cache.get(cache_key)
    if cached:
        return MedicamentStatistics(**cached)
    stats = await crud.get_statistics(db, categorie=categorie)
    cache.set(cache_key, stats, ttl=300)
    return MedicamentStatistics(**stats)


@router.get(
    "/dashboard",
    response_model=DashboardStatistics,
    summary="Dashboard enrichi",
    description="Statistiques enrichies avec top 10 laboratoires, top 10 pays, versions disponibles.",
    responses={
        200: {"description": "Dashboard complet"},
        403: {"description": "Pack insuffisant (INSTITUTIONNEL+ requis)", "content": {"application/json": {"example": {"detail": "Pack insuffisant. Requis : INSTITUTIONNEL ou DEVELOPPEUR."}}}},
    },
)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_INST_AND_UP)
):
    """Dashboard avec statistiques enrichies."""
    cached = cache.get("dashboard")
    if cached:
        return DashboardStatistics(**cached)
    stats = await crud.get_dashboard_statistics(db)
    cache.set("dashboard", stats, ttl=300)
    return DashboardStatistics(**stats)


@router.get(
    "/export",
    summary="Export CSV",
    description="Exporter les médicaments filtrés au format CSV.",
    responses={200: {"content": {"text/csv": {}}, "description": "Fichier CSV"}}
)
async def export_csv(
    categorie: Optional[str] = Query(None, description="Filtrer par catégorie"),
    version: Optional[str] = Query(None, description="Filtrer par version"),
    type: Optional[str] = Query(None, alias="type", description="Filtrer par type"),
    pays_laboratoire: Optional[str] = Query(None, description="Filtrer par pays"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_PRO_AND_UP)
):
    """Export CSV des médicaments avec filtres optionnels."""
    csv_content = await crud.export_medicaments_csv(
        db, categorie=categorie, version=version,
        type_medicament=type, pays_laboratoire=pays_laboratoire
    )
    
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=medicaments_export.csv"}
    )


@router.get(
    "/par-dci/{dci}",
    response_model=DCIGroupResponse,
    summary="Grouper par DCI",
    description="Retrouver tous les médicaments (génériques, référence, retraits) d'une même DCI.",
    responses={
        404: {"description": "DCI introuvable", "content": {"application/json": {"example": {"detail": "Aucun médicament trouvé pour la DCI: PARACETAMOL"}}}},
        403: {"description": "Pack insuffisant (PRO+ requis)"},
    },
)
async def get_by_dci(
    dci: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_PRO_AND_UP)
):
    """Tous les médicaments d'une même DCI (molécule)."""
    medicaments, total = await crud.get_medicaments_by_dci(db, dci)
    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucun médicament trouvé pour la DCI: {dci}"
        )
    return DCIGroupResponse(dci=dci, total=total, medicaments=medicaments)


@router.get(
    "/{medicament_id}",
    response_model=MedicamentOut,
    summary="Détail d'un médicament",
    description="Récupérer un médicament par son ID.",
    responses={
        404: {"description": "Médicament non trouvé", "content": {"application/json": {"example": {"detail": "Médicament non trouvé"}}}},
    },
)
async def get_medicament(
    medicament_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_FREE_AND_UP)
):
    """Détail d'un médicament par ID."""
    medicament = await crud.get_medicament_by_id(db, medicament_id)
    if not medicament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Médicament non trouvé"
        )
    return medicament


@router.post(
    "",
    response_model=MedicamentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un médicament",
    description="Créer un nouveau médicament. Requiert le rôle Admin.",
    responses={
        201: {"description": "Médicament créé"},
        403: {"description": "Admin requis"},
    },
)
async def create_medicament(
    medicament: MedicamentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Créer un médicament (Admin)."""
    result = await crud.create_medicament(db, medicament)
    cache.invalidate()  # Invalidate all stats caches
    return result


@router.put(
    "/{medicament_id}",
    response_model=MedicamentOut,
    summary="Mettre à jour un médicament",
    description="Mettre à jour un médicament existant. Requiert le rôle Admin.",
    responses={
        200: {"description": "Médicament mis à jour"},
        404: {"description": "Médicament non trouvé", "content": {"application/json": {"example": {"detail": "Médicament non trouvé"}}}},
    },
)
async def update_medicament(
    medicament_id: int,
    medicament_update: MedicamentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Mettre à jour un médicament (Admin)."""
    medicament = await crud.update_medicament(db, medicament_id, medicament_update)
    if not medicament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Médicament non trouvé"
        )
    cache.invalidate()
    return medicament


@router.delete(
    "/{medicament_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un médicament",
    description="Suppression logique (soft delete). Requiert le rôle Admin.",
    responses={
        204: {"description": "Médicament supprimé"},
        404: {"description": "Médicament non trouvé", "content": {"application/json": {"example": {"detail": "Médicament non trouvé"}}}},
    },
)
async def delete_medicament(
    medicament_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Supprimer un médicament - soft delete (Admin)."""
    deleted = await crud.delete_medicament(db, medicament_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Médicament non trouvé"
        )
    cache.invalidate()
    return None
