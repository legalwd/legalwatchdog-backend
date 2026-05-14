"""add GENERATING_TAXONOMY to campaignstatus enum

Revision ID: 767c7c05f76a
Revises: 52441cbb7dfa
Create Date: 2026-03-06 12:22:54.771121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '767c7c05f76a'
down_revision: Union[str, Sequence[str], None] = '52441cbb7dfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new enum value using ALTER TYPE.
    # Some postgres versions require this to be outside a transaction block, 
    # but Alembic typically handles this or it works directly in PG 12+.
    op.execute("ALTER TYPE campaignstatus ADD VALUE IF NOT EXISTS 'GENERATING_TAXONOMY'")


def downgrade() -> None:
    """Downgrade schema."""
    # Dropping a value from a Postgres ENUM is not supported natively 
    # without recreating the entire type, so we leave it as-is on downgrade.
    pass
