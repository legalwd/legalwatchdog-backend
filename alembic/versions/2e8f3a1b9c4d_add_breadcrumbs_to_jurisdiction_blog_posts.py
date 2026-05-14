"""add breadcrumbs field to jurisdiction_blog_posts

Revision ID: 2e8f3a1b9c4d
Revises: 6b629fc3f748
Create Date: 2026-04-26 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e8f3a1b9c4d"
down_revision: Union[str, Sequence[str], None] = "6b629fc3f748"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add breadcrumbs JSONB column to jurisdiction_blog_posts.

    Stores precomputed breadcrumb trail as [{"name": str, "url": str}, ...]
    for fast O(1) retrieval during HTML artifact rendering.
    """
    op.add_column(
        "jurisdiction_blog_posts",
        sa.Column("breadcrumbs", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    """Remove breadcrumbs column from jurisdiction_blog_posts."""
    op.drop_column("jurisdiction_blog_posts", "breadcrumbs")
