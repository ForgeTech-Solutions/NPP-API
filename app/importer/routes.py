"""Import routes for nomenclature."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional, List
import json

from app.importer.excel_parser import parse_excel_file, validate_medicament_record, get_available_sheets
from app.medicaments.models import Medicament
from app.medicaments.crud import clean_duplicates as crud_clean_duplicates
from app.models.import_log import ImportLog
from app.auth.models import User
from app.core.security import get_current_admin
from app.db.session import get_db
from pydantic import BaseModel

logger = logging.getLogger("nomenclature.import")

router = APIRouter(prefix="/import", tags=["Import"])


class SheetPreview(BaseModel):
    """Schema for sheet preview."""
    name: str
    rows: int
    detected_type: str
    detected_category: str = "unknown"
    columns: List[str]
    error: Optional[str] = None

    model_config = {"json_schema_extra": {"example": {
        "name": "Nomenclature",
        "rows": 8542,
        "detected_type": "medicaments",
        "detected_category": "NOMENCLATURE",
        "columns": ["N", "NUM_ENREGISTREMENT", "CODE", "DCI", "NOM_MARQUE", "FORME", "DOSAGE", "CONDITIONNEMENT", "LISTE", "LABORATOIRE", "PAYS_LABORATOIRE"],
        "error": None,
    }}}


class SheetsPreviewResponse(BaseModel):
    """Schema for sheets preview response."""
    filename: str
    sheets: List[SheetPreview]

    model_config = {"json_schema_extra": {"example": {
        "filename": "nomenclature_2025.xlsx",
        "sheets": [
            {"name": "Nomenclature", "rows": 8542, "detected_type": "medicaments", "detected_category": "NOMENCLATURE", "columns": ["N", "CODE", "DCI", "NOM_MARQUE"], "error": None},
            {"name": "Non Renouvelés", "rows": 1200, "detected_type": "medicaments", "detected_category": "NON_RENOUVELE", "columns": ["N", "CODE", "DCI", "NOM_MARQUE"], "error": None},
            {"name": "Retraits", "rows": 645, "detected_type": "medicaments", "detected_category": "RETRAIT", "columns": ["N", "CODE", "DCI", "NOM_MARQUE", "DATE_RETRAIT", "MOTIF_RETRAIT"], "error": None},
        ],
    }}}


class SheetImportResult(BaseModel):
    """Schema for single sheet import result."""
    rows_inserted: int
    rows_updated: int
    rows_ignored: int
    category: str
    errors: List[dict]

    model_config = {"json_schema_extra": {"example": {
        "rows_inserted": 8500, "rows_updated": 42, "rows_ignored": 3,
        "category": "NOMENCLATURE",
        "errors": [{"row": 156, "message": "Champ code manquant"}],
    }}}


class ImportResponse(BaseModel):
    """Schema for import response."""
    version_nomenclature: str
    source_fichier: str
    sheets_processed: dict[str, SheetImportResult]
    total_rows_inserted: int
    total_rows_updated: int
    available_sheets: List[str]

    model_config = {"json_schema_extra": {"example": {
        "version_nomenclature": "2025-06-30",
        "source_fichier": "nomenclature_2025.xlsx",
        "sheets_processed": {
            "Nomenclature": {"rows_inserted": 8500, "rows_updated": 42, "rows_ignored": 3, "category": "NOMENCLATURE", "errors": []},
            "Non Renouvelés": {"rows_inserted": 1200, "rows_updated": 0, "rows_ignored": 1, "category": "NON_RENOUVELE", "errors": []},
        },
        "total_rows_inserted": 9700, "total_rows_updated": 42,
        "available_sheets": ["Nomenclature", "Non Renouvelés", "Retraits"],
    }}}


class ImportResult:
    """Container for import operation results."""
    
    def __init__(self, version: str, filename: str):
        self.version_nomenclature = version
        self.source_fichier = filename
        self.sheets_processed = {}
        self.available_sheets = []
    
    def add_sheet_result(self, sheet_name: str, inserted: int, updated: int, ignored: int, errors: list, category: str = "NOMENCLATURE"):
        """Add result for a sheet."""
        self.sheets_processed[sheet_name] = {
            "rows_inserted": inserted,
            "rows_updated": updated,
            "rows_ignored": ignored,
            "category": category,
            "errors": errors
        }
    
    @property
    def total_rows_inserted(self) -> int:
        return sum(r["rows_inserted"] for r in self.sheets_processed.values())
    
    @property
    def total_rows_updated(self) -> int:
        return sum(r["rows_updated"] for r in self.sheets_processed.values())
    
    def to_dict(self):
        return {
            "version_nomenclature": self.version_nomenclature,
            "source_fichier": self.source_fichier,
            "sheets_processed": self.sheets_processed,
            "total_rows_inserted": self.total_rows_inserted,
            "total_rows_updated": self.total_rows_updated,
            "available_sheets": self.available_sheets
        }


@router.post(
    "/sheets/preview",
    response_model=SheetsPreviewResponse,
    summary="Prévisualiser les feuilles Excel",
    description="Voir les feuilles disponibles et leur catégorie détectée avant d'importer.",
    responses={
        400: {"description": "Fichier invalide", "content": {"application/json": {"example": {"detail": "Le fichier doit être un fichier Excel (.xlsx ou .xls)"}}}},
        500: {"description": "Erreur de lecture", "content": {"application/json": {"example": {"detail": "Erreur de lecture: Unsupported format"}}}},
    },
)
async def preview_excel_sheets(
    file: UploadFile = File(..., description="Fichier Excel à prévisualiser"),
    current_user: User = Depends(get_current_admin)
):
    """Prévisualiser les feuilles d'un fichier Excel."""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier doit être un fichier Excel (.xlsx ou .xls)"
        )
    
    try:
        file_content = await file.read()
        sheets = get_available_sheets(file_content)
        return SheetsPreviewResponse(
            filename=file.filename,
            sheets=[SheetPreview(**sheet) for sheet in sheets]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de lecture: {str(e)}"
        )


@router.post(
    "/nomenclature",
    summary="Importer la nomenclature",
    description="Importer toutes les feuilles d'un fichier Excel (Nomenclature, Non Renouvelés, Retraits). "
                "Chaque feuille est automatiquement catégorisée.",
    responses={
        200: {"description": "Import terminé", "content": {"application/json": {"example": {
            "version_nomenclature": "2025-06-30",
            "source_fichier": "nomenclature_2025.xlsx",
            "sheets_processed": {
                "Nomenclature": {"rows_inserted": 8500, "rows_updated": 42, "rows_ignored": 3, "category": "NOMENCLATURE", "errors": []},
            },
            "total_rows_inserted": 8500, "total_rows_updated": 42,
            "available_sheets": ["Nomenclature", "Non Renouvelés", "Retraits"],
        }}}},
        400: {"description": "Fichier ou feuilles invalides", "content": {"application/json": {"example": {"detail": "Le fichier doit être un fichier Excel (.xlsx ou .xls)"}}}},
    },
)
async def import_nomenclature(
    file: UploadFile = File(..., description="Fichier Excel de nomenclature"),
    version: str = Form(..., description="Version de la nomenclature (ex: 2025-06-30)"),
    sheet_names: Optional[str] = Form(None, description="Noms des feuilles à importer, séparés par virgule (vide = toutes)"),
    remplacer_version: bool = Form(False, description="Remplacer la version existante"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Importer la nomenclature depuis un fichier Excel (multi-feuilles)."""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier doit être un fichier Excel (.xlsx ou .xls)"
        )
    
    sheets_to_import = None
    if sheet_names:
        sheets_to_import = [s.strip() for s in sheet_names.split(',') if s.strip()]
    
    # Create import log
    import_log = ImportLog(
        version_nomenclature=version,
        source_fichier=file.filename,
        start_time=datetime.utcnow()
    )
    db.add(import_log)
    await db.commit()
    
    result = ImportResult(version=version, filename=file.filename)
    
    try:
        file_content = await file.read()
        available_sheets_info = get_available_sheets(file_content)
        result.available_sheets = [sheet["name"] for sheet in available_sheets_info]
        
        # Determine which sheets to process
        if sheets_to_import:
            available_names = set(result.available_sheets)
            invalid_sheets = [s for s in sheets_to_import if s not in available_names]
            if invalid_sheets:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feuilles invalides: {', '.join(invalid_sheets)}. Disponibles: {', '.join(result.available_sheets)}"
                )
            sheets_to_process = sheets_to_import
        else:
            # Process all sheets with type 'medicaments'
            sheets_to_process = [
                sheet["name"] for sheet in available_sheets_info 
                if sheet["detected_type"] == "medicaments"
            ]
            if not sheets_to_process:
                sheets_to_process = result.available_sheets
        
        logger.info(f"Import starting: {len(sheets_to_process)} sheets to process for version {version}")
        
        # If remplacer_version, soft delete existing entries
        if remplacer_version:
            update_result = await db.execute(
                select(Medicament).where(
                    Medicament.version_nomenclature == version,
                    Medicament.deleted == False
                )
            )
            existing_medicaments = update_result.scalars().all()
            for med in existing_medicaments:
                med.deleted = True
            await db.commit()
            logger.info(f"Soft-deleted {len(existing_medicaments)} existing entries for version {version}")
        
        # Process each sheet
        for sheet_name in sheets_to_process:
            sheet_inserted = 0
            sheet_updated = 0
            sheet_ignored = 0
            sheet_errors = []
            sheet_category = "NOMENCLATURE"
            
            try:
                records = parse_excel_file(file_content, sheet_name=sheet_name)
                
                if records:
                    sheet_category = records[0].get('categorie', 'NOMENCLATURE')
                
                for idx, record in enumerate(records, start=1):
                    try:
                        is_valid, validation_errors = validate_medicament_record(record)
                        if not is_valid:
                            sheet_errors.append({
                                "row": idx,
                                "message": "; ".join(validation_errors)
                            })
                            sheet_ignored += 1
                            continue
                        
                        record['version_nomenclature'] = version
                        record['source_fichier'] = file.filename
                        
                        # Check if medicament exists (by code + version + categorie)
                        existing = await db.execute(
                            select(Medicament).where(
                                Medicament.code == record['code'],
                                Medicament.version_nomenclature == version,
                                Medicament.categorie == record.get('categorie', 'NOMENCLATURE'),
                                Medicament.deleted == False
                            )
                        )
                        existing_meds = existing.scalars().all()
                        
                        if len(existing_meds) > 1:
                            sheet_errors.append({
                                "row": idx,
                                "message": f"Duplicate code '{record['code']}' ({len(existing_meds)} entries). Skipping."
                            })
                            sheet_ignored += 1
                            continue
                        elif len(existing_meds) == 1:
                            existing_med = existing_meds[0]
                            for key, value in record.items():
                                if key not in ['id', 'created_at']:
                                    setattr(existing_med, key, value)
                            sheet_updated += 1
                        else:
                            new_medicament = Medicament(**record)
                            db.add(new_medicament)
                            sheet_inserted += 1
                        
                        if (sheet_inserted + sheet_updated) % 100 == 0:
                            await db.commit()
                            
                    except Exception as e:
                        sheet_errors.append({
                            "row": idx,
                            "message": f"Error: {str(e)}"
                        })
                        sheet_ignored += 1
                        continue
                
                await db.commit()
                
                result.add_sheet_result(
                    sheet_name=sheet_name,
                    inserted=sheet_inserted,
                    updated=sheet_updated,
                    ignored=sheet_ignored,
                    errors=sheet_errors,
                    category=sheet_category,
                )
                
                logger.info(f"Sheet '{sheet_name}' ({sheet_category}): +{sheet_inserted} inserted, ~{sheet_updated} updated, -{sheet_ignored} ignored")
                
            except Exception as e:
                result.add_sheet_result(
                    sheet_name=sheet_name,
                    inserted=0, updated=0, ignored=0,
                    errors=[{"message": f"Failed to process sheet: {str(e)}"}],
                    category="unknown",
                )
                logger.error(f"Failed to process sheet '{sheet_name}': {e}")
                continue
        
        # Update import log
        import_log.end_time = datetime.utcnow()
        import_log.rows_inserted = result.total_rows_inserted
        import_log.rows_updated = result.total_rows_updated
        import_log.rows_ignored = sum(r["rows_ignored"] for r in result.sheets_processed.values())
        
        all_errors = []
        for sheet_name, sheet_result in result.sheets_processed.items():
            for error in sheet_result["errors"]:
                all_errors.append({"sheet": sheet_name, **error})
        
        import_log.errors = json.dumps(all_errors) if all_errors else None
        await db.commit()
        
        logger.info(f"Import complete: {result.total_rows_inserted} inserted, {result.total_rows_updated} updated")
        return result.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        import_log.end_time = datetime.utcnow()
        import_log.errors = json.dumps([{"message": str(e)}])
        await db.commit()
        logger.error(f"Import failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


@router.get(
    "/duplicates",
    summary="Détecter les doublons",
    description="Détecter les codes en double dans la base, groupés par code+version+catégorie.",
    responses={
        200: {"description": "Liste des doublons", "content": {"application/json": {"example": {
            "total_duplicates": 5,
            "duplicates": [
                {"code": "01 A 003", "version": "2025-06-30", "categorie": "NOMENCLATURE", "count": 3},
                {"code": "02 B 015", "version": "2025-06-30", "categorie": "NOMENCLATURE", "count": 2},
            ],
        }}}},
    },
)
async def detect_duplicates(
    version: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Détecter les codes en double."""
    from sqlalchemy import func
    
    query = select(
        Medicament.code,
        Medicament.version_nomenclature,
        Medicament.categorie,
        func.count(Medicament.id).label('count')
    ).where(Medicament.deleted == False)
    
    if version:
        query = query.where(Medicament.version_nomenclature == version)
    
    query = query.group_by(
        Medicament.code, Medicament.version_nomenclature, Medicament.categorie
    ).having(func.count(Medicament.id) > 1)
    
    result = await db.execute(query)
    duplicates = result.all()
    
    duplicates_list = [
        {"code": dup.code, "version": dup.version_nomenclature, 
         "categorie": dup.categorie, "count": dup.count}
        for dup in duplicates
    ]
    
    return {
        "total_duplicates": len(duplicates_list),
        "duplicates": duplicates_list
    }


@router.post(
    "/clean-duplicates",
    summary="Nettoyer les doublons",
    description="Nettoyer les doublons en gardant une seule entrée par code+version+catégorie. "
                "Par défaut en mode dry_run (simulation).",
    responses={
        200: {"description": "Résultat du nettoyage", "content": {"application/json": {"example": {
            "dry_run": True, "total_groups": 5,
            "total_entries_deleted": 8,
            "details": [{"code": "01 A 003", "version": "2025-06-30", "categorie": "NOMENCLATURE", "kept": 1, "deleted": 2}],
        }}}},
        400: {"description": "Stratégie invalide", "content": {"application/json": {"example": {"detail": "keep_strategy doit être 'latest' ou 'first'"}}}},
    },
)
async def clean_duplicates_endpoint(
    version: Optional[str] = None,
    keep_strategy: str = "latest",
    dry_run: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Nettoyer les doublons (dry_run par défaut)."""
    if keep_strategy not in ["latest", "first"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="keep_strategy doit être 'latest' ou 'first'"
        )
    
    result = await crud_clean_duplicates(db, version=version, keep_strategy=keep_strategy, dry_run=dry_run)
    logger.info(f"Clean duplicates: {result['total_entries_deleted']} deleted (dry_run={dry_run})")
    return result
