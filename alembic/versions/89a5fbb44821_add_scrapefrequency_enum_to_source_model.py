"""Add ScrapeFrequency enum to Source model

Revision ID: 89a5fbb44821
Revises: 3e7e5f7ae4aa
Create Date: 2025-11-23 21:08:53.943892

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '89a5fbb44821'
down_revision: Union[str, Sequence[str], None] = '3e7e5f7ae4aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the new ENUM type
scrapefrequency_enum = postgresql.ENUM('HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY', name='scrapefrequency')


def upgrade() -> None:
    """Upgrade schema."""
    # Create the ENUM type in the database
    scrapefrequency_enum.create(op.get_bind())

    # Alter the column to use the new ENUM type
    # The postgresql_using clause tells PostgreSQL how to cast the existing string values
    op.alter_column(
        'sources',
        'scrape_frequency',
        type_=scrapefrequency_enum,
        existing_type=sa.VARCHAR(),
        postgresql_using='scrape_frequency::text::scrapefrequency'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Alter the column back to VARCHAR
    op.alter_column(
        'sources',
        'scrape_frequency',
        type_=sa.VARCHAR(),
        existing_type=scrapefrequency_enum
    )

    # Drop the ENUM type from the database
    scrapefrequency_enum.drop(op.get_bind())
