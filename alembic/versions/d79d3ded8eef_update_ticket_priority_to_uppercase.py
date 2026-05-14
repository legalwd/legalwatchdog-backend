"""update_ticket_priority_and_status_to_uppercase

Revision ID: d79d3ded8eef
Revises: 79a4e5e7506c
Create Date: 2025-12-07 18:24:13.838314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd79d3ded8eef'
down_revision: Union[str, Sequence[str], None] = '79a4e5e7506c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update the priority enum type to uppercase
    op.execute("""
        ALTER TYPE ticketpriority RENAME TO ticketpriority_old;
        CREATE TYPE ticketpriority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
        ALTER TABLE tickets 
            ALTER COLUMN priority TYPE ticketpriority 
            USING (
                CASE priority::text
                    WHEN 'low' THEN 'LOW'
                    WHEN 'medium' THEN 'MEDIUM'
                    WHEN 'high' THEN 'HIGH'
                    WHEN 'critical' THEN 'CRITICAL'
                    ELSE priority::text
                END
            )::ticketpriority;
        DROP TYPE ticketpriority_old;
    """)
    
    # Update the status enum type to uppercase
    op.execute("""
        ALTER TYPE ticketstatus RENAME TO ticketstatus_old;
        CREATE TYPE ticketstatus AS ENUM ('OPEN', 'IN_PROGRESS', 'CLOSED');
        ALTER TABLE tickets 
            ALTER COLUMN status TYPE ticketstatus 
            USING (
                CASE status::text
                    WHEN 'open' THEN 'OPEN'
                    WHEN 'in_progress' THEN 'IN_PROGRESS'
                    WHEN 'closed' THEN 'CLOSED'
                    ELSE status::text
                END
            )::ticketstatus;
        DROP TYPE ticketstatus_old;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Revert priority enum values back to lowercase
    op.execute("""
        ALTER TYPE ticketpriority RENAME TO ticketpriority_old;
        CREATE TYPE ticketpriority AS ENUM ('low', 'medium', 'high', 'critical');
        ALTER TABLE tickets 
            ALTER COLUMN priority TYPE ticketpriority 
            USING (
                CASE priority::text
                    WHEN 'LOW' THEN 'low'
                    WHEN 'MEDIUM' THEN 'medium'
                    WHEN 'HIGH' THEN 'high'
                    WHEN 'CRITICAL' THEN 'critical'
                    ELSE priority::text
                END
            )::ticketpriority;
        DROP TYPE ticketpriority_old;
    """)
    
    # Revert status enum values back to lowercase
    op.execute("""
        ALTER TYPE ticketstatus RENAME TO ticketstatus_old;
        CREATE TYPE ticketstatus AS ENUM ('open', 'in_progress', 'closed');
        ALTER TABLE tickets 
            ALTER COLUMN status TYPE ticketstatus 
            USING (
                CASE status::text
                    WHEN 'OPEN' THEN 'open'
                    WHEN 'IN_PROGRESS' THEN 'in_progress'
                    WHEN 'CLOSED' THEN 'closed'
                    ELSE status::text
                END
            )::ticketstatus;
        DROP TYPE ticketstatus_old;
    """)
