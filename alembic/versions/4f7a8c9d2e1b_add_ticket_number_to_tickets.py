"""add ticket_number to tickets

Revision ID: 4f7a8c9d2e1b
Revises: f2db96071e38
Create Date: 2026-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f7a8c9d2e1b'
down_revision = 'f2db96071e38'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Add the column as nullable first (to allow backfill)
    op.add_column('tickets', sa.Column('ticket_number', sa.BIGINT(), nullable=True))

    # Step 2: Backfill existing tickets sequentially starting from 1001
    # Order by created_at, then id as fallback for deterministic ordering
    op.execute("""
        WITH numbered_tickets AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) + 1000 AS new_number
            FROM tickets
        )
        UPDATE tickets
        SET ticket_number = numbered_tickets.new_number
        FROM numbered_tickets
        WHERE tickets.id = numbered_tickets.id
    """)

    # Step 3: Create sequence owned by the column
    op.execute("""
        CREATE SEQUENCE tickets_ticket_number_seq OWNED BY tickets.ticket_number
    """)

    # Step 4: Set sequence value to MAX(ticket_number) so next value is MAX + 1
    op.execute("""
        SELECT setval('tickets_ticket_number_seq',
                      COALESCE((SELECT MAX(ticket_number) FROM tickets), 1000))
    """)

    # Step 5: Set the default value to use the sequence for new inserts
    op.alter_column('tickets', 'ticket_number',
                    server_default=sa.text("nextval('tickets_ticket_number_seq')"))

    # Step 6: Make the column NOT NULL now that all rows have values
    op.alter_column('tickets', 'ticket_number', nullable=False)

    # Step 7: Create unique constraint to prevent duplicates
    op.create_unique_constraint('uq_tickets_ticket_number', 'tickets', ['ticket_number'])


def downgrade():
    # Drop unique constraint
    op.drop_constraint('uq_tickets_ticket_number', 'tickets', type_='unique')

    # Remove default
    op.alter_column('tickets', 'ticket_number', server_default=None)

    # Drop sequence
    op.execute("DROP SEQUENCE IF EXISTS tickets_ticket_number_seq")

    # Drop column
    op.drop_column('tickets', 'ticket_number')
