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
    """Schema for medicament output.
    
    Example response:
        ```json
        {
            "id": 1,
            "code": "01 A 003",
            "dci": "CETIRIZINE DICHLORHYDRATE",
            "nom_marque": "ARTIZ",
            "categorie": "NOMENCLATURE",
            "type_medicament": "GE",
            "pays_laboratoire": "ALGERIE"
        }
        ```
    """
    id: int
    source_fichier: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


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


class DCIGroupResponse(BaseModel):
    """Schema for DCI group response."""
    dci: str
    total: int
    medicaments: List[MedicamentOut]
