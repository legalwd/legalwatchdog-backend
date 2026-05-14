"""add relationship for specialists model

Revision ID: c808117ae395
Revises: 6d9a7e1f4c3b
Create Date: 2026-01-07 20:00:08.494817

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c808117ae395'
down_revision: Union[str, Sequence[str], None] = '6d9a7e1f4c3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add SPECIALIST_REQUEST to the notificationtype enum
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'SPECIALIST_REQUEST'")

    # Make revision_id nullable in revision_notifications (for specialist hire notifications)
    op.alter_column(
        'revision_notifications',
        'revision_id',
        existing_type=sa.Uuid(),
        nullable=True,
    )

    # Delete existing specialist_hires records that don't have user_id
    op.execute("DELETE FROM specialist_hires")

    # Add project_id column and foreign key
    op.add_column('specialist_hires', sa.Column('project_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_specialist_hires_project_id',
        'specialist_hires',
        'projects',
        ['project_id'],
        ['id'],
    )

    # Add jurisdiction_id column and foreign key
    op.add_column('specialist_hires', sa.Column('jurisdiction_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_specialist_hires_jurisdiction_id',
        'specialist_hires',
        'jurisdictions',
        ['jurisdiction_id'],
        ['id'],
    )

    # Add user_id column and foreign key
    op.add_column('specialist_hires', sa.Column('user_id', sa.Uuid(), nullable=False))
    op.create_foreign_key(
        'fk_specialist_hires_user_id',
        'specialist_hires',
        'users',
        ['user_id'],
        ['id'],
    )

    # Add is_active column (defaults to True for new records)
    op.add_column('specialist_hires', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # Add deactivated_at column (nullable timestamp)
    op.add_column('specialist_hires', sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True))

    # Add specialist_hire_id column and foreign key to revision_notifications
    op.add_column('revision_notifications', sa.Column('specialist_hire_id', sa.Uuid(), nullable=True))
    op.create_index('ix_revision_notifications_specialist_hire_id', 'revision_notifications', ['specialist_hire_id'])
    op.create_foreign_key(
        'fk_revision_notifications_specialist_hire_id',
        'revision_notifications',
        'specialist_hires',
        ['specialist_hire_id'],
        ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove specialist_hire_id foreign key, index, and column from revision_notifications
    op.drop_constraint('fk_revision_notifications_specialist_hire_id', 'revision_notifications', type_='foreignkey')
    op.drop_index('ix_revision_notifications_specialist_hire_id', 'revision_notifications')
    op.drop_column('revision_notifications', 'specialist_hire_id')

    # Remove deactivated_at column
    op.drop_column('specialist_hires', 'deactivated_at')

    # Remove is_active column
    op.drop_column('specialist_hires', 'is_active')

    # Remove user_id foreign key and column
    op.drop_constraint('fk_specialist_hires_user_id', 'specialist_hires', type_='foreignkey')
    op.drop_column('specialist_hires', 'user_id')

    # Remove jurisdiction_id foreign key and column
    op.drop_constraint('fk_specialist_hires_jurisdiction_id', 'specialist_hires', type_='foreignkey')
    op.drop_column('specialist_hires', 'jurisdiction_id')

    # Remove project_id foreign key and column
    op.drop_constraint('fk_specialist_hires_project_id', 'specialist_hires', type_='foreignkey')
    op.drop_column('specialist_hires', 'project_id')

    # Revert revision_id to NOT NULL (note: will fail if any NULL values exist)
    op.alter_column(
        'revision_notifications',
        'revision_id',
        existing_type=sa.Uuid(),
        nullable=False,
    )
