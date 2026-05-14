"""add_profile_ui_fields

Revision ID: c898c3a02ef8
Revises: 03db9267c449
Create Date: 2025-11-28 16:33:52.100714

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c898c3a02ef8"
down_revision: Union[str, Sequence[str], None] = "88065553cd35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns to organizations table
    op.add_column("organizations", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("organizations", sa.Column("plan", sa.String(length=50), nullable=True))
    op.add_column("organizations", sa.Column("logo_url", sa.String(length=500), nullable=True))

    # Add columns to user_organizations table
    op.add_column("user_organizations", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column(
        "user_organizations", sa.Column("department", sa.String(length=100), nullable=True)
    )

    # Add column to users table
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns in reverse order
    op.drop_column("users", "avatar_url")
    op.drop_column("user_organizations", "department")
    op.drop_column("user_organizations", "title")
    op.drop_column("organizations", "logo_url")
    op.drop_column("organizations", "plan")
    op.drop_column("organizations", "location")
