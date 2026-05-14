"""add unique active org name index

Revision ID: f94d1e19a88c
Revises: eba4d89ad4c9
Create Date: 2025-12-01 19:01:26.205590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f94d1e19a88c'
down_revision: Union[str, Sequence[str], None] = 'eba4d89ad4c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create partial unique index on LOWER(name)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_organizations_active_name
        ON organizations (LOWER(name))
        WHERE deleted_at IS NULL;
    """)


def downgrade() -> None:
    # Drop the partial index
    op.execute("DROP INDEX IF EXISTS ux_organizations_active_name;")
