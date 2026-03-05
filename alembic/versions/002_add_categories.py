"""add categorie date_retrait motif_retrait columns

Revision ID: 002_add_categories
Revises: 
Create Date: 2025-01-01

This migration adds columns to support multi-sheet import:
- categorie: NOMENCLATURE / NON_RENOUVELE / RETRAIT
- date_retrait: Date of withdrawal (for RETRAIT category)
- motif_retrait: Reason for withdrawal
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_categories'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add categorie, date_retrait, motif_retrait columns to medicaments."""
    # Add categorie column with default
    op.add_column('medicaments', sa.Column('categorie', sa.String(50), nullable=False, server_default='NOMENCLATURE'))
    op.create_index('ix_medicaments_categorie', 'medicaments', ['categorie'])
    
    # Add date_retrait column (nullable)
    op.add_column('medicaments', sa.Column('date_retrait', sa.Date(), nullable=True))
    
    # Add motif_retrait column (nullable)
    op.add_column('medicaments', sa.Column('motif_retrait', sa.Text(), nullable=True))
    
    # Add composite indexes for common query patterns
    op.create_index('ix_medicaments_code_version', 'medicaments', ['code', 'version_nomenclature'])
    op.create_index('ix_medicaments_categorie_version', 'medicaments', ['categorie', 'version_nomenclature'])
    op.create_index('ix_medicaments_dci_nom', 'medicaments', ['dci', 'nom_marque'])


def downgrade() -> None:
    """Remove categorie, date_retrait, motif_retrait columns."""
    op.drop_index('ix_medicaments_dci_nom', table_name='medicaments')
    op.drop_index('ix_medicaments_categorie_version', table_name='medicaments')
    op.drop_index('ix_medicaments_code_version', table_name='medicaments')
    op.drop_index('ix_medicaments_categorie', table_name='medicaments')
    op.drop_column('medicaments', 'motif_retrait')
    op.drop_column('medicaments', 'date_retrait')
    op.drop_column('medicaments', 'categorie')
