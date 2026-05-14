"""add_field_mappings_table

Revision ID: 25bc91239c2a
Revises: b3c7018405fa
Create Date: 2026-01-01 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '25bc91239c2a'
down_revision: Union[str, Sequence[str], None] = 'b3c7018405fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add field_mappings table for LLM field normalization."""
    op.create_table(
        'field_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_field_name', sa.String(), nullable=False),
        sa.Column('canonical_field_name', sa.String(), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('approved', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient lookups
    op.create_index(
        'ix_field_mappings_source_id',
        'field_mappings',
        ['source_id']
    )
    op.create_index(
        'ix_field_mappings_original_field_name',
        'field_mappings',
        ['original_field_name']
    )
    op.create_index(
        'ix_field_mappings_canonical_field_name',
        'field_mappings',
        ['canonical_field_name']
    )
    
    # Create composite index for common query pattern
    op.create_index(
        'ix_field_mappings_source_original',
        'field_mappings',
        ['source_id', 'original_field_name']
    )


def downgrade() -> None:
    """Downgrade schema - remove field_mappings table."""
    op.drop_index('ix_field_mappings_source_original', table_name='field_mappings')
    op.drop_index('ix_field_mappings_canonical_field_name', table_name='field_mappings')
    op.drop_index('ix_field_mappings_original_field_name', table_name='field_mappings')
    op.drop_index('ix_field_mappings_source_id', table_name='field_mappings')
    op.drop_table('field_mappings')
