"""add_content_html_to_jurisdiction_blog_posts

Revision ID: 5488cdfb1498
Revises: b1fba7b51691
Create Date: 2026-02-18 12:50:44.993384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5488cdfb1498'
down_revision: Union[str, Sequence[str], None] = 'b1fba7b51691'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add content_html column to jurisdiction_blog_posts.

    Stores the pre-rendered HTML body fragment generated from the Markdown
    source at generation time. Backfilled to empty string for existing rows.
    """
    op.add_column(
        "jurisdiction_blog_posts",
        sa.Column("content_html", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("jurisdiction_blog_posts", "content_html", server_default=None)


def downgrade() -> None:
    """Remove content_html column from jurisdiction_blog_posts."""
    op.drop_column("jurisdiction_blog_posts", "content_html")
