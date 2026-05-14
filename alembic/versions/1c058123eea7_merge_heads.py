"""merge heads

Revision ID: 1c058123eea7
Revises: 1ab5a062c90b, 63f3c37453f1
Create Date: 2025-11-25 00:59:49.344713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c058123eea7'
down_revision: Union[str, Sequence[str], None] = ('1ab5a062c90b', '63f3c37453f1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
