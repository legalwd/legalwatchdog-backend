"""empty message

Revision ID: 4a9f5acf1625
Revises: b398f6b7c7db, fts_data_revision
Create Date: 2025-11-26 09:53:29.928707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a9f5acf1625'
down_revision: Union[str, Sequence[str], None] = ('b398f6b7c7db', 'fts_data_revision')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
