"""change enums in ticket model

Revision ID: 657231732a9b
Revises: 0fcbdabbf412
Create Date: 2025-12-06 20:01:04.805474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '657231732a9b'
down_revision: Union[str, Sequence[str], None] = '0fcbdabbf412'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Step 1: Use autocommit_block inside the function
    with op.get_context().autocommit_block():
        # Add new uppercase enum values
        op.execute("ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'OPEN'")
        op.execute("ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'IN_PROGRESS'")
        op.execute("ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'CLOSED'")

        op.execute("ALTER TYPE ticketpriority ADD VALUE IF NOT EXISTS 'LOW'")
        op.execute("ALTER TYPE ticketpriority ADD VALUE IF NOT EXISTS 'MEDIUM'")
        op.execute("ALTER TYPE ticketpriority ADD VALUE IF NOT EXISTS 'HIGH'")
        op.execute("ALTER TYPE ticketpriority ADD VALUE IF NOT EXISTS 'CRITICAL'")

        # Update existing data
        op.execute("UPDATE tickets SET status = 'OPEN' WHERE status = 'open'")
        op.execute("UPDATE tickets SET status = 'IN_PROGRESS' WHERE status = 'in_progress'")
        op.execute("UPDATE tickets SET status = 'CLOSED' WHERE status = 'closed'")

        op.execute("UPDATE tickets SET priority = 'LOW' WHERE priority = 'low'")
        op.execute("UPDATE tickets SET priority = 'MEDIUM' WHERE priority = 'medium'")
        op.execute("UPDATE tickets SET priority = 'HIGH' WHERE priority = 'high'")
        op.execute("UPDATE tickets SET priority = 'CRITICAL' WHERE priority = 'critical'")

    # Remove max_length constraint from title field
    op.alter_column('tickets', 'title',
                    existing_type=sa.String(length=255),
                    type_=sa.String(),
                    existing_nullable=False)


def downgrade() -> None:
    # Revert data to lowercase
    op.execute("UPDATE tickets SET status = 'open' WHERE status = 'OPEN'")
    op.execute("UPDATE tickets SET status = 'in_progress' WHERE status = 'IN_PROGRESS'")
    op.execute("UPDATE tickets SET status = 'closed' WHERE status = 'CLOSED'")

    op.execute("UPDATE tickets SET priority = 'low' WHERE priority = 'LOW'")
    op.execute("UPDATE tickets SET priority = 'medium' WHERE priority = 'MEDIUM'")
    op.execute("UPDATE tickets SET priority = 'high' WHERE priority = 'HIGH'")
    op.execute("UPDATE tickets SET priority = 'critical' WHERE priority = 'CRITICAL'")

    # Add back max_length constraint
    op.alter_column('tickets', 'title',
                    existing_type=sa.String(),
                    type_=sa.String(length=255),
                    existing_nullable=False)
