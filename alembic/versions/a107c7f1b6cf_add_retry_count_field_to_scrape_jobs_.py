"""Add retry_count field to scrape_jobs table

Revision ID: a107c7f1b6cf
Revises: 122ea317508a
Create Date: 2025-12-27 02:31:41.195091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a107c7f1b6cf'
down_revision: Union[str, Sequence[str], None] = '122ea317508a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add retry_count field to scrape_jobs table for limiting retry attempts
    # Add as nullable first, then populate existing rows, then make non-nullable
    op.add_column('scrape_jobs', sa.Column('retry_count', sa.Integer(), nullable=True))

    # Set default value of 0 for all existing jobs
    op.execute("UPDATE scrape_jobs SET retry_count = 0 WHERE retry_count IS NULL")

    # Make the column non-nullable
    op.alter_column('scrape_jobs', 'retry_count', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove retry_count field from scrape_jobs table
    op.drop_column('scrape_jobs', 'retry_count')
