"""CRUD operations for Medicament model."""
import csv
import io
import logging
from typing import Optional, List, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, text
from datetime import date

from app.medicaments.models import Medicament
from app.medicaments.schemas import MedicamentCreate, MedicamentUpdate

logger = logging.getLogger("nomenclature.crud")

# Normalization maps
TYPE_NORMALIZATION = {
    "GÉ": "GE", "Gé": "GE", "gé": "GE", "ge": "GE", "GENERIQUE": "GE", "GÉNÉRIQUE": "GE",
    "RE": "RE", "Re": "RE", "re": "RE", "REFERENCE": "RE", "RÉFÉRENCE": "RE",
    "BIO": "BIO", "Bio": "BIO", "bio": "BIO", "BIOLOGIQUE": "BIO",
}

PAYS_NORMALIZATION = {
    "ALGÉRIE": "ALGERIE", "Algérie": "ALGERIE", "algerie": "ALGERIE", "Algerie": "ALGERIE",
    "FRANCE": "FRANCE", "France": "FRANCE",
    "INDE": "INDE", "Inde": "INDE",
    "JORDANIE": "JORDANIE", "Jordanie": "JORDANIE",
    "ALLEMAGNE": "ALLEMAGNE", "Allemagne": "ALLEMAGNE",
    "ROYAUME-UNI": "ROYAUME-UNI", "Royaume-Uni": "ROYAUME-UNI",
    "SUISSE": "SUISSE", "Suisse": "SUISSE",
    "ITALIE": "ITALIE", "Italie": "ITALIE",
    "TURQUIE": "TURQUIE", "Turquie": "TURQUIE",
    "PAYS-BAS": "PAYS-BAS", "Pays-Bas": "PAYS-BAS",
    "ESPAGNE": "ESPAGNE", "Espagne": "ESPAGNE",
    "ETATS-UNIS": "ETATS-UNIS", "États-Unis": "ETATS-UNIS", "ÉTATS-UNIS": "ETATS-UNIS",
}


def normalize_type(value: str) -> str:
    """Normalize type_medicament to uppercase standard."""
    if not value:
        return "ND"
    v = value.strip()
    return TYPE_NORMALIZATION.get(v, v.upper())


def normalize_pays(value: str) -> str:
    """Normalize pays_laboratoire to uppercase without accents."""
    if not value:
        return "ND"
    v = value.strip()
    return PAYS_NORMALIZATION.get(v, v.upper())


def normalize_string_upper(value: Optional[str]) -> Optional[str]:
    """Normalize a string to uppercase stripped."""
    if not value:
        return value
    return value.strip().upper()


# Valid sort columns
SORT_COLUMNS = {
    "id": Medicament.id,
    "code": Medicament.code,
    "dci": Medicament.dci,
    "nom_marque": Medicament.nom_marque,
    "laboratoire": Medicament.laboratoire,
    "pays_laboratoire": Medicament.pays_laboratoire,
    "type_medicament": Medicament.type_medicament,
    "statut": Medicament.statut,
    "categorie": Medicament.categorie,
    "date_enregistrement_initial": Medicament.date_enregistrement_initial,
    "created_at": Medicament.created_at,
}


async def get_medicament_by_id(db: AsyncSession, medicament_id: int) -> Optional[Medicament]:
    """Get a medicament by ID (excluding deleted ones)."""
    result = await db.execute(
        select(Medicament).where(
            and_(
                Medicament.id == medicament_id,
                Medicament.deleted == False
            )
        )
    )
    return result.scalar_one_or_none()


async def get_medicaments(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
    q: Optional[str] = None,
    dci: Optional[str] = None,
    nom_marque: Optional[str] = None,
    code: Optional[str] = None,
    num_enregistrement: Optional[str] = None,
    laboratoire: Optional[str] = None,
    pays_laboratoire: Optional[str] = None,
    liste: Optional[str] = None,
    type_medicament: Optional[str] = None,
    statut: Optional[str] = None,
    categorie: Optional[str] = None,
    date_initial_min: Optional[date] = None,
    date_initial_max: Optional[date] = None,
    version: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc"
) -> tuple[List[Medicament], int]:
    """
    Get paginated and filtered list of medicaments with sorting.
    
    Supports full-text search on DCI, nom_marque, code, and laboratoire.
    """
    # Base query - exclude deleted
    query = select(Medicament).where(Medicament.deleted == False)
    
    # Full-text search across multiple fields
    if q:
        search_pattern = f"%{q}%"
        query = query.where(
            or_(
                Medicament.dci.ilike(search_pattern),
                Medicament.nom_marque.ilike(search_pattern),
                Medicament.code.ilike(search_pattern),
                Medicament.laboratoire.ilike(search_pattern),
            )
        )
    
    # Individual field filters
    if dci:
        query = query.where(Medicament.dci.ilike(f"%{dci}%"))
    if nom_marque:
        query = query.where(Medicament.nom_marque.ilike(f"%{nom_marque}%"))
    if code:
        query = query.where(Medicament.code.ilike(f"%{code}%"))
    if num_enregistrement:
        query = query.where(Medicament.num_enregistrement.ilike(f"%{num_enregistrement}%"))
    if laboratoire:
        query = query.where(Medicament.laboratoire.ilike(f"%{laboratoire}%"))
    if pays_laboratoire:
        query = query.where(Medicament.pays_laboratoire.ilike(f"%{pays_laboratoire}%"))
    if liste:
        query = query.where(Medicament.liste == liste)
    if type_medicament:
        query = query.where(Medicament.type_medicament == type_medicament.upper())
    if statut:
        query = query.where(Medicament.statut == statut.upper())
    if categorie:
        query = query.where(Medicament.categorie == categorie.upper())
    if date_initial_min:
        query = query.where(Medicament.date_enregistrement_initial >= date_initial_min)
    if date_initial_max:
        query = query.where(Medicament.date_enregistrement_initial <= date_initial_max)
    if version:
        query = query.where(Medicament.version_nomenclature == version)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply sorting
    sort_column = SORT_COLUMNS.get(sort_by, Medicament.id)
    if order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    medicaments = result.scalars().all()
    
    logger.debug(f"Query returned {len(medicaments)} medicaments (total: {total})")
    return list(medicaments), total


async def create_medicament(db: AsyncSession, medicament: MedicamentCreate) -> Medicament:
    """Create a new medicament with normalization."""
    data = medicament.model_dump()
    data['type_medicament'] = normalize_type(data.get('type_medicament', ''))
    data['pays_laboratoire'] = normalize_pays(data.get('pays_laboratoire', ''))
    
    db_medicament = Medicament(**data)
    db.add(db_medicament)
    await db.commit()
    await db.refresh(db_medicament)
    logger.info(f"Created medicament: {db_medicament.code} - {db_medicament.nom_marque}")
    return db_medicament


async def update_medicament(
    db: AsyncSession,
    medicament_id: int,
    medicament_update: MedicamentUpdate
) -> Optional[Medicament]:
    """Update a medicament with normalization."""
    db_medicament = await get_medicament_by_id(db, medicament_id)
    if not db_medicament:
        return None
    
    update_data = medicament_update.model_dump(exclude_unset=True)
    if 'type_medicament' in update_data and update_data['type_medicament']:
        update_data['type_medicament'] = normalize_type(update_data['type_medicament'])
    if 'pays_laboratoire' in update_data and update_data['pays_laboratoire']:
        update_data['pays_laboratoire'] = normalize_pays(update_data['pays_laboratoire'])
    
    for field, value in update_data.items():
        setattr(db_medicament, field, value)
    
    await db.commit()
    await db.refresh(db_medicament)
    logger.info(f"Updated medicament {medicament_id}: {db_medicament.code}")
    return db_medicament


async def delete_medicament(db: AsyncSession, medicament_id: int) -> bool:
    """Soft delete a medicament (set deleted = True)."""
    db_medicament = await get_medicament_by_id(db, medicament_id)
    if not db_medicament:
        return False
    
    db_medicament.deleted = True
    await db.commit()
    logger.info(f"Soft-deleted medicament {medicament_id}")
    return True


async def get_statistics(db: AsyncSession, categorie: Optional[str] = None) -> dict:
    """Get medicament statistics with optional category filter."""
    base_filter = [Medicament.deleted == False]
    if categorie:
        base_filter.append(Medicament.categorie == categorie.upper())
    
    total_result = await db.execute(select(func.count(Medicament.id)).where(*base_filter))
    total = total_result.scalar()
    
    lab_result = await db.execute(
        select(Medicament.laboratoire, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.laboratoire)
    )
    par_laboratoire = {row[0]: row[1] for row in lab_result.all()}
    
    pays_result = await db.execute(
        select(Medicament.pays_laboratoire, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.pays_laboratoire)
    )
    par_pays = {row[0]: row[1] for row in pays_result.all()}
    
    type_result = await db.execute(
        select(Medicament.type_medicament, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.type_medicament)
    )
    par_type = {row[0]: row[1] for row in type_result.all()}
    
    cat_result = await db.execute(
        select(Medicament.categorie, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.categorie)
    )
    par_categorie = {row[0]: row[1] for row in cat_result.all()}
    
    statut_result = await db.execute(
        select(Medicament.statut, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.statut)
    )
    par_statut = {row[0]: row[1] for row in statut_result.all()}
    
    return {
        "total": total,
        "par_laboratoire": par_laboratoire,
        "par_pays": par_pays,
        "par_type": par_type,
        "par_categorie": par_categorie,
        "par_statut": par_statut,
    }


async def get_dashboard_statistics(db: AsyncSession) -> dict:
    """Get enriched dashboard statistics."""
    base_filter = [Medicament.deleted == False]
    
    total_result = await db.execute(select(func.count(Medicament.id)).where(*base_filter))
    total = total_result.scalar()
    
    lab_count = await db.execute(
        select(func.count(func.distinct(Medicament.laboratoire))).where(*base_filter)
    )
    total_labs = lab_count.scalar()
    
    pays_count = await db.execute(
        select(func.count(func.distinct(Medicament.pays_laboratoire))).where(*base_filter)
    )
    total_pays = pays_count.scalar()
    
    cat_result = await db.execute(
        select(Medicament.categorie, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.categorie)
    )
    par_categorie = {row[0]: row[1] for row in cat_result.all()}
    
    type_result = await db.execute(
        select(Medicament.type_medicament, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.type_medicament)
    )
    par_type = {row[0]: row[1] for row in type_result.all()}
    
    statut_result = await db.execute(
        select(Medicament.statut, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.statut)
    )
    par_statut = {row[0]: row[1] for row in statut_result.all()}
    
    top_lab_result = await db.execute(
        select(Medicament.laboratoire, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.laboratoire)
        .order_by(desc(func.count(Medicament.id))).limit(10)
    )
    top_10_laboratoires = [{"laboratoire": row[0], "count": row[1]} for row in top_lab_result.all()]
    
    top_pays_result = await db.execute(
        select(Medicament.pays_laboratoire, func.count(Medicament.id).label('count'))
        .where(*base_filter).group_by(Medicament.pays_laboratoire)
        .order_by(desc(func.count(Medicament.id))).limit(10)
    )
    top_10_pays = [{"pays": row[0], "count": row[1]} for row in top_pays_result.all()]
    
    versions_result = await db.execute(
        select(func.distinct(Medicament.version_nomenclature))
        .where(*base_filter).order_by(Medicament.version_nomenclature.desc())
    )
    versions = [row[0] for row in versions_result.all()]
    
    return {
        "total_medicaments": total,
        "total_laboratoires": total_labs,
        "total_pays": total_pays,
        "par_categorie": par_categorie,
        "par_type": par_type,
        "par_statut": par_statut,
        "top_10_laboratoires": top_10_laboratoires,
        "top_10_pays": top_10_pays,
        "versions_disponibles": versions,
    }


async def get_medicaments_by_dci(db: AsyncSession, dci: str) -> tuple[List[Medicament], int]:
    """Get all medicaments grouped by DCI (all generics of the same molecule)."""
    query = select(Medicament).where(
        and_(Medicament.dci.ilike(f"%{dci}%"), Medicament.deleted == False)
    ).order_by(Medicament.categorie, Medicament.nom_marque)
    
    result = await db.execute(query)
    medicaments = result.scalars().all()
    return list(medicaments), len(medicaments)


async def export_medicaments_csv(
    db: AsyncSession,
    categorie: Optional[str] = None,
    version: Optional[str] = None,
    type_medicament: Optional[str] = None,
    pays_laboratoire: Optional[str] = None,
) -> str:
    """Export filtered medicaments to CSV string."""
    query = select(Medicament).where(Medicament.deleted == False)
    if categorie:
        query = query.where(Medicament.categorie == categorie.upper())
    if version:
        query = query.where(Medicament.version_nomenclature == version)
    if type_medicament:
        query = query.where(Medicament.type_medicament == type_medicament.upper())
    if pays_laboratoire:
        query = query.where(Medicament.pays_laboratoire.ilike(f"%{pays_laboratoire}%"))
    
    query = query.order_by(Medicament.code)
    result = await db.execute(query)
    medicaments = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "code", "num_enregistrement", "dci", "nom_marque", "forme", "dosage",
        "conditionnement", "liste", "p1", "p2", "obs", "laboratoire",
        "pays_laboratoire", "date_enregistrement_initial", "date_enregistrement_final",
        "type_medicament", "statut", "duree_stabilite", "categorie",
        "date_retrait", "motif_retrait", "version_nomenclature"
    ])
    for med in medicaments:
        writer.writerow([
            med.id, med.code, med.num_enregistrement, med.dci, med.nom_marque,
            med.forme, med.dosage, med.conditionnement, med.liste, med.p1, med.p2,
            med.obs, med.laboratoire, med.pays_laboratoire,
            med.date_enregistrement_initial, med.date_enregistrement_final,
            med.type_medicament, med.statut, med.duree_stabilite, med.categorie,
            med.date_retrait, med.motif_retrait, med.version_nomenclature
        ])
    
    logger.info(f"Exported {len(medicaments)} medicaments to CSV")
    return output.getvalue()


async def clean_duplicates(
    db: AsyncSession,
    version: Optional[str] = None,
    keep_strategy: str = "latest",
    dry_run: bool = True
) -> dict:
    """Clean duplicate codes - keep one entry per code+version+categorie."""
    if keep_strategy not in ["latest", "first"]:
        raise ValueError("keep_strategy must be 'latest' or 'first'")
    
    dup_query = select(
        Medicament.code, Medicament.version_nomenclature, Medicament.categorie,
        func.count(Medicament.id).label('count')
    ).where(Medicament.deleted == False)
    
    if version:
        dup_query = dup_query.where(Medicament.version_nomenclature == version)
    
    dup_query = dup_query.group_by(
        Medicament.code, Medicament.version_nomenclature, Medicament.categorie,
    ).having(func.count(Medicament.id) > 1)
    
    dup_result = await db.execute(dup_query)
    duplicates = dup_result.all()
    
    cleaned = []
    total_deleted = 0
    
    for dup in duplicates:
        entries_query = select(Medicament).where(
            Medicament.code == dup.code,
            Medicament.version_nomenclature == dup.version_nomenclature,
            Medicament.categorie == dup.categorie,
            Medicament.deleted == False
        ).order_by(
            Medicament.created_at.desc() if keep_strategy == "latest" else Medicament.created_at.asc()
        )
        entries_result = await db.execute(entries_query)
        entries = entries_result.scalars().all()
        
        if len(entries) > 1:
            kept = entries[0]
            for entry in entries[1:]:
                if not dry_run:
                    entry.deleted = True
                total_deleted += 1
            cleaned.append({
                "code": dup.code, "version": dup.version_nomenclature,
                "categorie": dup.categorie, "total_found": len(entries),
                "kept_id": kept.id, "deleted_count": len(entries) - 1,
            })
    
    if not dry_run:
        await db.commit()
        logger.info(f"Cleaned {total_deleted} duplicates (strategy: {keep_strategy})")
    
    return {
        "dry_run": dry_run, "keep_strategy": keep_strategy,
        "total_duplicate_groups": len(cleaned),
        "total_entries_deleted": total_deleted, "cleaned": cleaned
    }
