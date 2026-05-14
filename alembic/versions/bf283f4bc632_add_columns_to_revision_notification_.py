"""add columns to revision notification table

Revision ID: bf283f4bc632
Revises: e051c40163e2
Create Date: 2025-12-04 20:21:46.774095

"""
from typing import Sequence, Union
import sqlmodel
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bf283f4bc632'
down_revision: Union[str, Sequence[str], None] = 'e051c40163e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Create the enum type explicitly
    notification_type_enum = postgresql.ENUM(
        'MENTION', 'CHANGE_DETECTED', 'SCRAPE_FAILED', name='notificationtype'
    )
    notification_type_enum.create(op.get_bind())

    # 2. Add columns
    op.add_column('revision_notifications', sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False))
    op.add_column('revision_notifications', sa.Column('source_id', sa.Uuid(), nullable=True))
    op.add_column('revision_notifications', sa.Column('notification_type', notification_type_enum, nullable=False))
    op.add_column('revision_notifications', sa.Column('organization_id', sa.Uuid(), nullable=True))
    op.add_column('revision_notifications', sa.Column('change_diff_id', sa.Uuid(), nullable=True))
    op.add_column('revision_notifications', sa.Column('action_url', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True))
    op.add_column('revision_notifications', sa.Column('read_at', sa.DateTime(timezone=True), nullable=True))

    # 3. Alter existing columns
    op.alter_column('revision_notifications', 'status',
               existing_type=postgresql.ENUM('PENDING', 'SENT', 'FAILED', name='notificationstatus'),
               type_=sa.String(),
               existing_nullable=False)
    op.alter_column('revision_notifications', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=False)
    op.alter_column('revision_notifications', 'sent_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)

    # 4. Create indexes and foreign keys
    op.create_index('ix_notifications_type_created', 'revision_notifications', ['notification_type', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('ix_notifications_unread', 'revision_notifications', ['user_id'], unique=False, postgresql_where=sa.text('read_at IS NULL'))
    op.create_index('ix_notifications_user_created', 'revision_notifications', ['user_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index('ix_notifications_user_status', 'revision_notifications', ['user_id', 'status'], unique=False, postgresql_where=sa.text('read_at IS NULL'))
    op.create_index(op.f('ix_revision_notifications_change_diff_id'), 'revision_notifications', ['change_diff_id'], unique=False)
    op.create_index(op.f('ix_revision_notifications_organization_id'), 'revision_notifications', ['organization_id'], unique=False)
    op.create_index(op.f('ix_revision_notifications_revision_id'), 'revision_notifications', ['revision_id'], unique=False)
    op.create_index(op.f('ix_revision_notifications_source_id'), 'revision_notifications', ['source_id'], unique=False)
    op.create_index(op.f('ix_revision_notifications_status'), 'revision_notifications', ['status'], unique=False)
    op.create_foreign_key(None, 'revision_notifications', 'organizations', ['organization_id'], ['id'])
    op.create_foreign_key(None, 'revision_notifications', 'sources', ['source_id'], ['id'])
    op.create_foreign_key(None, 'revision_notifications', 'change_diff', ['change_diff_id'], ['diff_id'])


def downgrade() -> None:
    """Downgrade schema."""

    # Drop added columns and indexes first
    op.drop_constraint(None, 'revision_notifications', type_='foreignkey')
    op.drop_constraint(None, 'revision_notifications', type_='foreignkey')
    op.drop_constraint(None, 'revision_notifications', type_='foreignkey')
    op.drop_index(op.f('ix_revision_notifications_status'), table_name='revision_notifications')
    op.drop_index(op.f('ix_revision_notifications_source_id'), table_name='revision_notifications')
    op.drop_index(op.f('ix_revision_notifications_revision_id'), table_name='revision_notifications')
    op.drop_index(op.f('ix_revision_notifications_organization_id'), table_name='revision_notifications')
    op.drop_index(op.f('ix_revision_notifications_change_diff_id'), table_name='revision_notifications')
    op.drop_index('ix_notifications_user_status', table_name='revision_notifications', postgresql_where=sa.text('read_at IS NULL'))
    op.drop_index('ix_notifications_user_created', table_name='revision_notifications')
    op.drop_index('ix_notifications_unread', table_name='revision_notifications', postgresql_where=sa.text('read_at IS NULL'))
    op.drop_index('ix_notifications_type_created', table_name='revision_notifications')

    # Drop columns
    op.drop_column('revision_notifications', 'read_at')
    op.drop_column('revision_notifications', 'action_url')
    op.drop_column('revision_notifications', 'change_diff_id')
    op.drop_column('revision_notifications', 'organization_id')
    op.drop_column('revision_notifications', 'notification_type')
    op.drop_column('revision_notifications', 'source_id')
    op.drop_column('revision_notifications', 'title')

    # Drop enum type
    notification_type_enum = postgresql.ENUM(
        'MENTION', 'CHANGE_DETECTED', 'SCRAPE_FAILED', name='notificationtype'
    )
    notification_type_enum.drop(op.get_bind())
    # ### end Alembic commands ###
