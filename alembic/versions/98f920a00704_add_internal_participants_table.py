"""Add internal_participants table for tracking invited users.

Revision ID: 98f920a00704
Revises: 48f920a00709
Create Date: 2026-01-02 00:00:00.000000

"""
from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '98f920a00704'
down_revision: Union[str, Sequence[str], None] = '48f920a00709'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the internal_participants table
    op.create_table(
        'internal_participants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('invited_by_user_id', sa.UUID(), nullable=False),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    # Create indices
    op.create_index('ix_internal_participants_ticket_id', 'internal_participants', ['ticket_id'], unique=False)
    op.create_index('ix_internal_participants_user_id', 'internal_participants', ['user_id'], unique=False)
    op.create_index('ix_internal_participants_invited_by_user_id', 'internal_participants', ['invited_by_user_id'], unique=False)


def downgrade() -> None:
    # Drop indices
    op.drop_index('ix_internal_participants_invited_by_user_id', table_name='internal_participants')
    op.drop_index('ix_internal_participants_user_id', table_name='internal_participants')
    op.drop_index('ix_internal_participants_ticket_id', table_name='internal_participants')
    # Drop the table
    op.drop_table('internal_participants')
