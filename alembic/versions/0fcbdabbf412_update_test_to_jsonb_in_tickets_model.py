"""change ticket content column from Text to JSONB

Revision ID: 0fcbdabbf412
Revises: 2d55398ccd09
Create Date: 2025-12-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0fcbdabbf412'
down_revision: Union[str, Sequence[str], None] = '2d55398ccd09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely convert TEXT → JSONB using a cast
    op.alter_column(
        'tickets',
        'content',
        type_=postgresql.JSONB(),
        postgresql_using='content::jsonb',
        existing_type=sa.Text(),
        nullable=True
    )


def downgrade() -> None:
    # Convert JSONB → TEXT
    op.alter_column(
        'tickets',
        'content',
        type_=sa.Text(),
        postgresql_using='content::text',
        existing_type=postgresql.JSONB(),
        nullable=True
    )
