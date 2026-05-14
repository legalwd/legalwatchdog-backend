"""make user_id nullable in parallel_usage_logs

Revision ID: f2db96071e38
Revises: a1b2c3d4e5f6
Create Date: 2026-01-08 05:14:18.460924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2db96071e38'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make user_id nullable in parallel_usage_logs."""
    op.alter_column('parallel_usage_logs', 'user_id',
                    existing_type=sa.Uuid(),
                    nullable=True)


def downgrade() -> None:
    """Revert user_id to not nullable in parallel_usage_logs."""
    op.alter_column('parallel_usage_logs', 'user_id',
                    existing_type=sa.Uuid(),
                    nullable=False)
