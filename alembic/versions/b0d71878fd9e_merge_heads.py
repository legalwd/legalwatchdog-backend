"""Merge heads

Revision ID: b0d71878fd9e
Revises: 7388a6aaaa8d, 8db953970cc0
Create Date: 2025-11-26 12:10:55.828027

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0d71878fd9e'
down_revision: Union[str, Sequence[str], None] = ('7388a6aaaa8d', '8db953970cc0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
