"""add ticket_created flag to data_revisions

Revision ID: 6d9a7e1f4c3b
Revises: 4f7a8c9d2e1b
Create Date: 2026-01-08 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6d9a7e1f4c3b'
down_revision = '4f7a8c9d2e1b'
branch_labels = None
depends_on = None


def upgrade():
    # Add ticket_created column with default FALSE
    op.add_column('data_revisions',
                  sa.Column('ticket_created', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Drop the column
    op.drop_column('data_revisions', 'ticket_created')
