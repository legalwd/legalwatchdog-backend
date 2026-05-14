"""create external_participants table for guest access

Revision ID: f1a2b3c4d5e6
Revises: a249039be841
Create Date: 2025-12-05 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a249039be841'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create external_participants table for guest access to tickets.

    This table stores NON-USERS who are invited to tickets via magic links.
    They do NOT have accounts and access via JWT tokens.
    """

    # Drop the old ticket_invited_users table if it exists (from previous migration)
    op.execute("DROP TABLE IF EXISTS ticket_invited_users CASCADE")

    # Create the external_participants table
    op.execute("""
        CREATE TABLE IF NOT EXISTS external_participants (
            id UUID PRIMARY KEY,
            ticket_id UUID NOT NULL,
            email VARCHAR(255) NOT NULL,
            role VARCHAR(100) NOT NULL DEFAULT 'Guest',
            token_hash VARCHAR(255),
            invited_by_user_id UUID NOT NULL,
            invited_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            last_accessed_at TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN NOT NULL DEFAULT true,
            expires_at TIMESTAMP WITH TIME ZONE
        )
    """)

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_participants_id ON external_participants (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_participants_ticket_id ON external_participants (ticket_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_participants_email ON external_participants (email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_external_participants_invited_by_user_id ON external_participants (invited_by_user_id)")

    # Add foreign key constraints
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tickets') THEN
                ALTER TABLE external_participants
                ADD CONSTRAINT fk_external_participants_ticket_id
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users') THEN
                ALTER TABLE external_participants
                ADD CONSTRAINT fk_external_participants_invited_by_user_id
                FOREIGN KEY (invited_by_user_id) REFERENCES users(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)

    # Create unique constraint to prevent duplicate email invitations per ticket
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_external_participants_ticket_email
        ON external_participants (ticket_id, LOWER(email))
    """)


def downgrade() -> None:
    """Revert external_participants table."""

    # Drop the external_participants table
    op.execute("DROP TABLE IF EXISTS external_participants CASCADE")

    # Optionally recreate ticket_invited_users if needed
    # (commented out since we're moving away from this model)
    # op.execute("""
    #     CREATE TABLE IF NOT EXISTS ticket_invited_users (
    #         ticket_id UUID NOT NULL,
    #         user_id UUID NOT NULL,
    #         invited_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    #         PRIMARY KEY (ticket_id, user_id)
    #     )
    # """)
