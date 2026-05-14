"""add blog_generation_jobs table

Revision ID: b1fba7b51691
Revises: 74515bb85d44
Create Date: 2026-02-17 13:50:25.743315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1fba7b51691'
down_revision: Union[str, Sequence[str], None] = '74515bb85d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('blog_generation_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('jurisdiction_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', name='bloggenerationjobstatus'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['jurisdictions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blog_generation_jobs_id'), 'blog_generation_jobs', ['id'], unique=False)
    op.create_index('ix_blog_generation_jobs_jurisdiction_active', 'blog_generation_jobs', ['jurisdiction_id'], unique=True, postgresql_where=sa.text("status IN ('PENDING', 'IN_PROGRESS')"))
    op.create_index(op.f('ix_blog_generation_jobs_jurisdiction_id'), 'blog_generation_jobs', ['jurisdiction_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_blog_generation_jobs_jurisdiction_id'), table_name='blog_generation_jobs')
    op.drop_index('ix_blog_generation_jobs_jurisdiction_active', table_name='blog_generation_jobs', postgresql_where=sa.text("status IN ('PENDING', 'IN_PROGRESS')"))
    op.drop_index(op.f('ix_blog_generation_jobs_id'), table_name='blog_generation_jobs')
    op.drop_table('blog_generation_jobs')
    op.execute("DROP TYPE IF EXISTS bloggenerationjobstatus")
