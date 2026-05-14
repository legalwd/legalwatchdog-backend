"""Merge heads

Revision ID: 5ee1506b7eab
Revises: 7900eb2a90aa, 35b26f6345aa
Create Date: 2025-11-26 16:53:24.788244

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ee1506b7eab'
down_revision: Union[str, Sequence[str], None] = ('7900eb2a90aa', '35b26f6345aa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
