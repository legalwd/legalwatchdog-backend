"""make hashed_password nullable

Revision ID: 84a91f4f3ead
Revises: 03db9267c449
Create Date: 2025-11-27 23:37:03.538910
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "84a91f4f3ead"
down_revision: Union[str, Sequence[str], None] = "03db9267c449"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
   
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.VARCHAR(length=255),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.VARCHAR(length=255),
        nullable=False,
    )

