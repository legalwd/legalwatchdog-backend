"""add_soft_delete_to_user_organizations

Revision ID: fa7a4d7cccac
Revises: c898c3a02ef8
Create Date: 2025-11-28 21:32:20.587151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa7a4d7cccac'
down_revision: Union[str, Sequence[str], None] = 'c898c3a02ef8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add soft delete columns to user_organizations table
    op.add_column("user_organizations", sa.Column("is_deleted", sa.Boolean(), nullable=True))
    op.add_column(
        "user_organizations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )

    # Set default values for existing rows
    op.execute("UPDATE user_organizations SET is_deleted = FALSE WHERE is_deleted IS NULL")

    # Make is_deleted NOT NULL after setting defaults
    op.alter_column("user_organizations", "is_deleted", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove soft delete columns
    op.drop_column("user_organizations", "deleted_at")
    op.drop_column("user_organizations", "is_deleted")
