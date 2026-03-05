"""Medicament database model."""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, Index
from app.db.base import Base


class Medicament(Base):
    """Medicament model for pharmaceutical nomenclature."""
    
    __tablename__ = "medicaments"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Nomenclature fields
    n = Column(Integer, nullable=True)  # Numéro de ligne
    num_enregistrement = Column(String(255), nullable=True, index=True)
    code = Column(String(100), nullable=False, index=True)
    dci = Column(Text, nullable=False)
    nom_marque = Column(Text, nullable=False)
    forme = Column(Text, nullable=False)
    dosage = Column(Text, nullable=False)
    conditionnement = Column(Text, nullable=False)
    liste = Column(String(100), nullable=True, index=True)
    p1 = Column(String(100), nullable=True)
    p2 = Column(String(100), nullable=True)
    obs = Column(Text, nullable=True)
    laboratoire = Column(Text, nullable=False)
    pays_laboratoire = Column(String(255), nullable=False, index=True)
    date_enregistrement_initial = Column(Date, nullable=True)
    date_enregistrement_final = Column(Date, nullable=True)
    type_medicament = Column(String(100), nullable=False, index=True)
    statut = Column(String(50), nullable=False, index=True)
    duree_stabilite = Column(Text, nullable=True)
    
    # Categorie: NOMENCLATURE, NON_RENOUVELE, RETRAIT
    categorie = Column(String(50), nullable=False, default="NOMENCLATURE", index=True)
    
    # Retrait-specific fields
    date_retrait = Column(Date, nullable=True)
    motif_retrait = Column(Text, nullable=True)
    
    # Metadata fields
    version_nomenclature = Column(String(50), nullable=False, index=True)
    source_fichier = Column(String(255), nullable=True)
    deleted = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Composite indexes for performance
    __table_args__ = (
        Index('ix_medicaments_code_version', 'code', 'version_nomenclature'),
        Index('ix_medicaments_categorie_version', 'categorie', 'version_nomenclature'),
        Index('ix_medicaments_dci_nom', 'dci', 'nom_marque'),
    )
    
    def __repr__(self) -> str:
        return f"<Medicament(id={self.id}, code={self.code}, dci={self.dci}, nom_marque={self.nom_marque}, categorie={self.categorie})>"
