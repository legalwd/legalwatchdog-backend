"""add_generated_at_and_generation_model_to_blog_posts

Revision ID: 74515bb85d44
Revises: fc25d327a91f
Create Date: 2026-02-15 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "74515bb85d44"
down_revision: Union[str, Sequence[str], None] = "fc25d327a91f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add generation_model and generated_at columns to blog posts."""
    op.add_column(
        "jurisdiction_blog_posts",
        sa.Column("generation_model", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "jurisdiction_blog_posts",
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove generation_model and generated_at columns from blog posts."""
    op.drop_column("jurisdiction_blog_posts", "generated_at")
    op.drop_column("jurisdiction_blog_posts", "generation_model")
