"""add_change_diff_id_to_tickets

Revision ID: 7810240dba0c
Revises: f1a2b3c4d5e6
Create Date: 2025-12-05 13:29:21.255218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7810240dba0c'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add change_diff_id column to tickets table
    op.add_column(
        'tickets',
        sa.Column('change_diff_id', sa.UUID(), nullable=True)
    )
    op.create_index(
        op.f('ix_tickets_change_diff_id'),
        'tickets',
        ['change_diff_id'],
        unique=False
    )
    op.create_foreign_key(
        'fk_tickets_change_diff_id_change_diff',
        'tickets',
        'change_diff',
        ['change_diff_id'],
        ['diff_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove foreign key, index, and column
    op.drop_constraint('fk_tickets_change_diff_id_change_diff', 'tickets', type_='foreignkey')
    op.drop_index(op.f('ix_tickets_change_diff_id'), table_name='tickets')
    op.drop_column('tickets', 'change_diff_id')
