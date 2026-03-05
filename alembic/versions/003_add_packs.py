"""add pack, is_approved, quotas, organisation to users

Revision ID: 003_add_packs
Revises: 002_add_categories
Create Date: 2026-03-05

Adds:
 - pack enum column (FREE/PRO/INSTITUTIONNEL/DEVELOPPEUR)
 - is_approved boolean (default False for new signups)
 - requests_today / requests_month / last_request_date (rate limiting)
 - organisation (optional, free text)
"""
from alembic import op
import sqlalchemy as sa


revision = '003_add_packs'
down_revision = '002_add_categories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pack column
    op.add_column('users', sa.Column('pack', sa.String(50), nullable=False, server_default='FREE'))
    op.create_index('ix_users_pack', 'users', ['pack'])

    # Approval
    op.add_column('users', sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='1'))

    # Rate limiting
    op.add_column('users', sa.Column('requests_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('requests_month', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('last_request_date', sa.Date(), nullable=True))

    # Organisation
    op.add_column('users', sa.Column('organisation', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'organisation')
    op.drop_column('users', 'last_request_date')
    op.drop_column('users', 'requests_month')
    op.drop_column('users', 'requests_today')
    op.drop_index('ix_users_pack', table_name='users')
    op.drop_column('users', 'is_approved')
    op.drop_column('users', 'pack')
