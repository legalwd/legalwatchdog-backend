"""add_extraction_status_enum

Revision ID: 83cde4a08354
Revises: 20dfc5b10985
Create Date: 2025-12-25 15:04:53.137461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '83cde4a08354'
down_revision: Union[str, Sequence[str], None] = '24ab90129d1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the extraction_status_enum type first
    extraction_status_enum = sa.Enum(
        'pending_extraction',
        'extracting',
        'completed',
        'extraction_failed',
        name='extraction_status_enum'
    )
    extraction_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Add extraction_status column to data_revisions
    op.add_column(
        'data_revisions',
        sa.Column(
            'extraction_status',
            extraction_status_enum,
            server_default='pending_extraction',
            nullable=False
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('data_revisions', 'extraction_status')
    sa.Enum(name='extraction_status_enum').drop(op.get_bind(), checkfirst=True)
