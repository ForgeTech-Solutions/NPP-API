"""Pydantic schemas for Medicament model."""
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date
from typing import Optional, List, Generic, TypeVar, Literal


class MedicamentBase(BaseModel):
    """Base Medicament schema.
    
    Represents a pharmaceutical product from the national nomenclature.
    """
    n: Optional[int] = Field(None, description="Numéro de ligne dans le fichier source", examples=[1])
    num_enregistrement: Optional[str] = Field(None, description="Numéro d'enregistrement", examples=["352/01 A 003/06/22"])
    code: str = Field(..., description="Code produit", examples=["01 A 003"])
    dci: str = Field(..., description="Dénomination Commune Internationale", examples=["CETIRIZINE DICHLORHYDRATE"])
    nom_marque: str = Field(..., description="Nom de marque commercial", examples=["ARTIZ"])
    forme: str = Field(..., description="Forme pharmaceutique", examples=["COMPRIME PELLICULE SECABLE"])
    dosage: str = Field(..., description="Dosage", examples=["10MG"])
    conditionnement: str = Field(..., description="Conditionnement", examples=["B/10"])
    liste: Optional[str] = Field(None, description="Liste (I, II, etc.)", examples=["LISTE II"])
    p1: Optional[str] = Field(None, description="P1 (HOP/OFF)", examples=["HOP"])
    p2: Optional[str] = Field(None, description="P2 (HOP/OFF)", examples=["OFF"])
    obs: Optional[str] = Field(None, description="Observations")
    laboratoire: str = Field(..., description="Laboratoire détenteur", examples=["EL KENDI"])
    pays_laboratoire: str = Field(..., description="Pays du laboratoire", examples=["ALGERIE"])
    date_enregistrement_initial: Optional[date] = Field(None, description="Date d'enregistrement initial")
    date_enregistrement_final: Optional[date] = Field(None, description="Date d'enregistrement final")
    type_medicament: str = Field(..., description="Type: GE (Générique), RE (Référence), BIO (Biologique)", examples=["GE"])
    statut: str = Field(..., description="Statut d'enregistrement", examples=["F"])
    duree_stabilite: Optional[str] = Field(None, description="Durée de stabilité", examples=["60 MOIS"])
    categorie: str = Field("NOMENCLATURE", description="Catégorie: NOMENCLATURE, NON_RENOUVELE, RETRAIT", examples=["NOMENCLATURE"])
    date_retrait: Optional[date] = Field(None, description="Date de retrait (si applicable)")
    motif_retrait: Optional[str] = Field(None, description="Motif de retrait (si applicable)")
    version_nomenclature: str = Field(..., description="Version de la nomenclature", examples=["2025-06-30"])


class MedicamentCreate(MedicamentBase):
    """Schema for creating a new medicament.
    
    Example:
        ```json
        {
            "code": "01 A 003",
            "dci": "CETIRIZINE DICHLORHYDRATE",
            "nom_marque": "ARTIZ",
            "forme": "COMPRIME",
            "dosage": "10MG",
            "conditionnement": "B/10",
            "laboratoire": "EL KENDI",
            "pays_laboratoire": "ALGERIE",
            "type_medicament": "GE",
            "statut": "F",
            "version_nomenclature": "2025-06-30"
        }
        ```
    """
    pass


class MedicamentUpdate(BaseModel):
    """Schema for updating a medicament (all fields optional)."""
    n: Optional[int] = None
    num_enregistrement: Optional[str] = None
    code: Optional[str] = None
    dci: Optional[str] = None
    nom_marque: Optional[str] = None
    forme: Optional[str] = None
    dosage: Optional[str] = None
    conditionnement: Optional[str] = None
    liste: Optional[str] = None
    p1: Optional[str] = None
    p2: Optional[str] = None
    obs: Optional[str] = None
    laboratoire: Optional[str] = None
    pays_laboratoire: Optional[str] = None
    date_enregistrement_initial: Optional[date] = None
    date_enregistrement_final: Optional[date] = None
    type_medicament: Optional[str] = None
    statut: Optional[str] = None
    duree_stabilite: Optional[str] = None
    categorie: Optional[str] = None
    date_retrait: Optional[date] = None
    motif_retrait: Optional[str] = None
    version_nomenclature: Optional[str] = None


class MedicamentOut(MedicamentBase):
    """Schema for medicament output."""
    id: int
    source_fichier: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {
            "id": 1542,
            "n": 1,
            "num_enregistrement": "352/01 A 003/06/22",
            "code": "01 A 003",
            "dci": "CETIRIZINE DICHLORHYDRATE",
            "nom_marque": "ARTIZ",
            "forme": "COMPRIME PELLICULE SECABLE",
            "dosage": "10MG",
            "conditionnement": "B/10",
            "liste": "LISTE II",
            "p1": "HOP",
            "p2": "OFF",
            "obs": None,
            "laboratoire": "EL KENDI",
            "pays_laboratoire": "ALGERIE",
            "date_enregistrement_initial": "2022-06-15",
            "date_enregistrement_final": "2027-06-15",
            "type_medicament": "GE",
            "statut": "F",
            "duree_stabilite": "60 MOIS",
            "categorie": "NOMENCLATURE",
            "date_retrait": None,
            "motif_retrait": None,
            "version_nomenclature": "2025-06-30",
            "source_fichier": "nomenclature_2025.xlsx",
            "created_at": "2026-01-10T09:00:00",
            "updated_at": "2026-01-10T09:00:00",
        }},
    )


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response schema with navigation info."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int = Field(description="Nombre total de pages")
    has_next: bool = Field(description="Indique s'il y a une page suivante")
    has_previous: bool = Field(description="Indique s'il y a une page précédente")

    model_config = ConfigDict(json_schema_extra={"example": {
        "items": ["(liste de médicaments)"],
        "total": 12345,
        "page": 1,
        "page_size": 50,
        "total_pages": 247,
        "has_next": True,
        "has_previous": False,
    }})


class MedicamentStatistics(BaseModel):
    """Schema for medicament statistics.
    
    Returns counts grouped by laboratory, country, type and category.
    """
    total: int = Field(description="Nombre total de médicaments")
    par_laboratoire: dict[str, int] = Field(description="Répartition par laboratoire")
    par_pays: dict[str, int] = Field(description="Répartition par pays")
    par_type: dict[str, int] = Field(description="Répartition par type (GE, RE, BIO)")
    par_categorie: dict[str, int] = Field(description="Répartition par catégorie")
    par_statut: dict[str, int] = Field(description="Répartition par statut")

    model_config = ConfigDict(json_schema_extra={"example": {
        "total": 12345,
        "par_laboratoire": {"BIOPHARM": 820, "EL KENDI": 654, "SAIDAL": 1120, "SANOFI": 530},
        "par_pays": {"ALGERIE": 5200, "FRANCE": 2100, "INDE": 1800, "JORDANIE": 900},
        "par_type": {"GE": 8500, "RE": 3200, "BIO": 645},
        "par_categorie": {"NOMENCLATURE": 10200, "NON_RENOUVELE": 1500, "RETRAIT": 645},
        "par_statut": {"F": 11000, "I": 1345},
    }})


class DashboardStatistics(BaseModel):
    """Schema for enriched dashboard statistics."""
    total_medicaments: int
    total_laboratoires: int
    total_pays: int
    par_categorie: dict[str, int]
    par_type: dict[str, int]
    par_statut: dict[str, int]
    top_10_laboratoires: List[dict]
    top_10_pays: List[dict]
    versions_disponibles: List[str]

    model_config = ConfigDict(json_schema_extra={"example": {
        "total_medicaments": 12345,
        "total_laboratoires": 380,
        "total_pays": 42,
        "par_categorie": {"NOMENCLATURE": 10200, "NON_RENOUVELE": 1500, "RETRAIT": 645},
        "par_type": {"GE": 8500, "RE": 3200, "BIO": 645},
        "par_statut": {"F": 11000, "I": 1345},
        "top_10_laboratoires": [
            {"laboratoire": "SAIDAL", "count": 1120},
            {"laboratoire": "BIOPHARM", "count": 820},
        ],
        "top_10_pays": [
            {"pays": "ALGERIE", "count": 5200},
            {"pays": "FRANCE", "count": 2100},
        ],
        "versions_disponibles": ["2025-06-30", "2024-12-31"],
    }})


class DCIGroupResponse(BaseModel):
    """Schema for DCI group response."""
    dci: str
    total: int
    medicaments: List[MedicamentOut]

    model_config = ConfigDict(json_schema_extra={"example": {
        "dci": "CETIRIZINE DICHLORHYDRATE",
        "total": 5,
        "medicaments": [
            {
                "id": 1542, "code": "01 A 003", "dci": "CETIRIZINE DICHLORHYDRATE",
                "nom_marque": "ARTIZ", "forme": "COMPRIME PELLICULE SECABLE",
                "dosage": "10MG", "conditionnement": "B/10",
                "laboratoire": "EL KENDI", "pays_laboratoire": "ALGERIE",
                "type_medicament": "GE", "statut": "F",
                "categorie": "NOMENCLATURE", "version_nomenclature": "2025-06-30",
                "created_at": "2026-01-10T09:00:00", "updated_at": "2026-01-10T09:00:00",
            }
        ],
    }})
