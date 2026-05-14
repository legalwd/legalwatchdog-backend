"""add_project_id_to_usage_logs

Revision ID: 48f920a00709
Revises: a107c7f1b6cf
Create Date: 2025-12-30 02:19:10.573654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '48f920a00709'
down_revision: Union[str, Sequence[str], None] = 'a107c7f1b6cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add project_id to llm_usage_logs and parallel_usage_logs tables."""
    # Add project_id to llm_usage_logs
    op.add_column('llm_usage_logs', sa.Column('project_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_llm_usage_logs_project_id'), 'llm_usage_logs', ['project_id'], unique=False)
    op.create_foreign_key('fk_llm_usage_logs_project_id', 'llm_usage_logs', 'projects', ['project_id'], ['id'])
    
    # Add project_id to parallel_usage_logs
    op.add_column('parallel_usage_logs', sa.Column('project_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_parallel_usage_logs_project_id'), 'parallel_usage_logs', ['project_id'], unique=False)
    op.create_foreign_key('fk_parallel_usage_logs_project_id', 'parallel_usage_logs', 'projects', ['project_id'], ['id'])


def downgrade() -> None:
    """Remove project_id from llm_usage_logs and parallel_usage_logs tables."""
    # Remove project_id from parallel_usage_logs
    op.drop_constraint('fk_parallel_usage_logs_project_id', 'parallel_usage_logs', type_='foreignkey')
    op.drop_index(op.f('ix_parallel_usage_logs_project_id'), table_name='parallel_usage_logs')
    op.drop_column('parallel_usage_logs', 'project_id')
    
    # Remove project_id from llm_usage_logs
    op.drop_constraint('fk_llm_usage_logs_project_id', 'llm_usage_logs', type_='foreignkey')
    op.drop_index(op.f('ix_llm_usage_logs_project_id'), table_name='llm_usage_logs')
    op.drop_column('llm_usage_logs', 'project_id')
