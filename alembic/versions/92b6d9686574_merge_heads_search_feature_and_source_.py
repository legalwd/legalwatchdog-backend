"""merge heads: search feature and source updates

Revision ID: 92b6d9686574
Revises: 4a9f5acf1625, 8db953970cc0
Create Date: 2025-11-26 11:55:57.542098

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92b6d9686574'
down_revision: Union[str, Sequence[str], None] = ('4a9f5acf1625', '8db953970cc0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
