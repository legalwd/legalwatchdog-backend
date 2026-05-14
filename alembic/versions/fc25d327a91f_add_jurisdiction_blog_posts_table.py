"""Add jurisdiction_blog_posts table

Revision ID: fc25d327a91f
Revises: 4a8b21c3d5e7
Create Date: 2026-02-14 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fc25d327a91f'
down_revision: Union[str, Sequence[str], None] = '4a8b21c3d5e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create jurisdiction_blog_posts table
    op.create_table(
        'jurisdiction_blog_posts',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            'jurisdiction_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('meta_description', sa.String(length=160), nullable=False),
        sa.Column(
            'keywords',
            postgresql.JSON(),
            nullable=False,
            server_default='[]',
        ),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['jurisdiction_id'],
            ['jurisdictions.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jurisdiction_id', name='uq_jurisdiction_blog_post'),
        sa.UniqueConstraint('slug', name='uq_blog_post_slug'),
    )
    op.create_index(
        'ix_jurisdiction_blog_posts_id',
        'jurisdiction_blog_posts',
        ['id'],
        unique=False,
    )
    op.create_index(
        'ix_jurisdiction_blog_posts_jurisdiction_id',
        'jurisdiction_blog_posts',
        ['jurisdiction_id'],
        unique=False,
    )
    op.create_index(
        'ix_jurisdiction_blog_posts_slug',
        'jurisdiction_blog_posts',
        ['slug'],
        unique=False,
    )
    op.create_index(
        'ix_jurisdiction_blog_posts_content_hash',
        'jurisdiction_blog_posts',
        ['content_hash'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_jurisdiction_blog_posts_content_hash',
        table_name='jurisdiction_blog_posts',
    )
    op.drop_index(
        'ix_jurisdiction_blog_posts_slug',
        table_name='jurisdiction_blog_posts',
    )
    op.drop_index(
        'ix_jurisdiction_blog_posts_jurisdiction_id',
        table_name='jurisdiction_blog_posts',
    )
    op.drop_index(
        'ix_jurisdiction_blog_posts_id',
        table_name='jurisdiction_blog_posts',
    )
    op.drop_table('jurisdiction_blog_posts')
