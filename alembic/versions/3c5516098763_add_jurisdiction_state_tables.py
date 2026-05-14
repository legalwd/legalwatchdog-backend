"""add_jurisdiction_state_tables

Revision ID: 3c5516098763
Revises: c7f2e4b6a9d0
Create Date: 2026-02-12 22:58:59.287802

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3c5516098763'
down_revision: Union[str, Sequence[str], None] = 'c7f2e4b6a9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands manually generated ###
    op.create_table('jurisdiction_states',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('jurisdiction_id', sa.Uuid(), nullable=False),
        sa.Column('field_key', sa.String(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('source_evidence', sa.JSON(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('originating_job_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['confirmed_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id'], ),
        sa.ForeignKeyConstraint(['originating_job_id'], ['jurisdiction_scrape_jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_jurisdiction_states_field_key'),
        'jurisdiction_states', ['field_key'], unique=False,
    )
    op.create_index(
        op.f('ix_jurisdiction_states_id'),
        'jurisdiction_states', ['id'], unique=False,
    )
    op.create_index(
        op.f('ix_jurisdiction_states_jurisdiction_id'),
        'jurisdiction_states', ['jurisdiction_id'], unique=False,
    )

    op.create_table('jurisdiction_state_history',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('state_id', sa.Uuid(), nullable=False),
        sa.Column('previous_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('changed_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('change_reason', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['state_id'], ['jurisdiction_states.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_jurisdiction_state_history_state_id'),
        'jurisdiction_state_history', ['state_id'], unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands manually generated ###
    op.drop_index(
        op.f('ix_jurisdiction_state_history_state_id'),
        table_name='jurisdiction_state_history',
    )
    op.drop_table('jurisdiction_state_history')
    op.drop_index(
        op.f('ix_jurisdiction_states_jurisdiction_id'),
        table_name='jurisdiction_states',
    )
    op.drop_index(op.f('ix_jurisdiction_states_id'), table_name='jurisdiction_states')
    op.drop_index(op.f('ix_jurisdiction_states_field_key'), table_name='jurisdiction_states')
    op.drop_table('jurisdiction_states')
    # ### end Alembic commands ###
