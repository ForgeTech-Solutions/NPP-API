"""add full_name, phone, signup_message to users

Revision ID: 004_add_signup_fields
Revises: 003_add_packs
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "004_add_signup_fields"
down_revision = "003_add_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(255), nullable=False, server_default=""))
    op.add_column("users", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("signup_message", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "signup_message")
    op.drop_column("users", "phone")
    op.drop_column("users", "full_name")
