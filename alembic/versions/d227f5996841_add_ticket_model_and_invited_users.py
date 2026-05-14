"""add ticket model and invited users

Revision ID: d227f5996841
Revises: c18bded7b6a0
Create Date: 2025-12-05 00:47:35.827101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd227f5996841'
down_revision: Union[str, Sequence[str], None] = 'c18bded7b6a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum types for ticket status and priority (if not exist)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ticketstatus AS ENUM ('open', 'in_progress', 'resolved', 'closed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ticketpriority AS ENUM ('low', 'medium', 'high', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create tickets table without foreign key constraints (since referenced tables may not exist yet)
    op.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id UUID PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            content TEXT,
            status ticketstatus NOT NULL,
            priority ticketpriority NOT NULL,
            is_manual BOOLEAN NOT NULL DEFAULT true,
            source_id UUID,
            data_revision_id UUID,
            created_by_user_id UUID,
            assigned_by_user_id UUID,
            assigned_to_user_id UUID,
            organization_id UUID NOT NULL,
            project_id UUID NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE,
            closed_at TIMESTAMP WITH TIME ZONE
        )
    """)
    
    # Create indexes for tickets
    op.execute("CREATE INDEX IF NOT EXISTS ix_tickets_assigned_to_user_id ON tickets (assigned_to_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tickets_created_by_user_id ON tickets (created_by_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tickets_organization_id ON tickets (organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tickets_project_id ON tickets (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tickets_status ON tickets (status)")
    
    # Create ticket_invited_users join table
    op.execute("""
        CREATE TABLE IF NOT EXISTS ticket_invited_users (
            ticket_id UUID NOT NULL,
            user_id UUID NOT NULL,
            invited_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (ticket_id, user_id)
        )
    """)
    
    # Add foreign key constraints only if the referenced tables exist
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users') THEN
                ALTER TABLE tickets 
                ADD CONSTRAINT fk_tickets_assigned_by_user_id FOREIGN KEY (assigned_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
                ALTER TABLE tickets 
                ADD CONSTRAINT fk_tickets_assigned_to_user_id FOREIGN KEY (assigned_to_user_id) REFERENCES users(id) ON DELETE SET NULL;
                ALTER TABLE tickets 
                ADD CONSTRAINT fk_tickets_created_by_user_id FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
                ALTER TABLE ticket_invited_users 
                ADD CONSTRAINT fk_ticket_invited_users_ticket_id FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE;
                ALTER TABLE ticket_invited_users 
                ADD CONSTRAINT fk_ticket_invited_users_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'data_revisions') THEN
                ALTER TABLE tickets 
                ADD CONSTRAINT fk_tickets_data_revision_id FOREIGN KEY (data_revision_id) REFERENCES data_revisions(id) ON DELETE SET NULL;
            ELSIF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'data_revision') THEN
                ALTER TABLE tickets 
                ADD CONSTRAINT fk_tickets_data_revision_id FOREIGN KEY (data_revision_id) REFERENCES data_revision(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'organizations') THEN
                ALTER TABLE tickets 
                ADD CONSTRAINT fk_tickets_organization_id FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'projects') THEN
                ALTER TABLE tickets 
                ADD CONSTRAINT fk_tickets_project_id FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'sources') THEN
                ALTER TABLE tickets 
                ADD CONSTRAINT fk_tickets_source_id FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables
    op.drop_table('ticket_invited_users')
    op.drop_index('ix_tickets_status', 'tickets')
    op.drop_index('ix_tickets_project_id', 'tickets')
    op.drop_index('ix_tickets_organization_id', 'tickets')
    op.drop_index('ix_tickets_created_by_user_id', 'tickets')
    op.drop_index('ix_tickets_assigned_to_user_id', 'tickets')
    op.drop_table('tickets')
    
    # Drop enum types
    op.execute('DROP TYPE ticketpriority')
    op.execute('DROP TYPE ticketstatus')
