"""add cascade to relationships for sources

Revision ID: b3c7018405fa
Revises: 98f920a00704
Create Date: 2026-01-02 21:11:05.475693

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3c7018405fa'
down_revision: Union[str, Sequence[str], None] = '98f920a00704'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CASCADE delete to all foreign keys."""
    
    # 1. ChangeDiff: Add CASCADE to both revision foreign keys
    op.drop_constraint('change_diff_new_revision_id_fkey', 'change_diff', type_='foreignkey')
    op.drop_constraint('change_diff_old_revision_id_fkey', 'change_diff', type_='foreignkey')
    
    op.create_foreign_key(
        'change_diff_new_revision_id_fkey',
        'change_diff', 'data_revisions',
        ['new_revision_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'change_diff_old_revision_id_fkey',
        'change_diff', 'data_revisions',
        ['old_revision_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # 2. DataRevisions: Add CASCADE to source_id
    op.drop_constraint('data_revisions_source_id_fkey', 'data_revisions', type_='foreignkey')
    op.create_foreign_key(
        'data_revisions_source_id_fkey',
        'data_revisions', 'sources',
        ['source_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # 3. ScrapeJob: Add CASCADE to source_id and data_revision_id
    op.drop_constraint('scrape_jobs_source_id_fkey', 'scrape_jobs', type_='foreignkey')
    op.drop_constraint('scrape_jobs_data_revision_id_fkey', 'scrape_jobs', type_='foreignkey')
    
    op.create_foreign_key(
        'scrape_jobs_source_id_fkey',
        'scrape_jobs', 'sources',
        ['source_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'scrape_jobs_data_revision_id_fkey',
        'scrape_jobs', 'data_revisions',
        ['data_revision_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # 4. Tickets: Add CASCADE to both source_id and data_revision_id
    op.drop_constraint('tickets_source_id_fkey', 'tickets', type_='foreignkey')
    op.drop_constraint('tickets_data_revision_id_fkey', 'tickets', type_='foreignkey')
    
    op.create_foreign_key(
        'tickets_source_id_fkey',
        'tickets', 'sources',
        ['source_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'tickets_data_revision_id_fkey',
        'tickets', 'data_revisions',
        ['data_revision_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # 5. RevisionNotifications: Add CASCADE to revision_id
    op.drop_constraint('revision_notifications_revision_id_fkey', 'revision_notifications', type_='foreignkey')
    op.create_foreign_key(
        'revision_notifications_revision_id_fkey',
        'revision_notifications', 'data_revisions',
        ['revision_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Remove CASCADE delete from all foreign keys."""
    
    # Revert all changes
    op.drop_constraint('change_diff_new_revision_id_fkey', 'change_diff', type_='foreignkey')
    op.drop_constraint('change_diff_old_revision_id_fkey', 'change_diff', type_='foreignkey')
    op.drop_constraint('data_revisions_source_id_fkey', 'data_revisions', type_='foreignkey')
    op.drop_constraint('scrape_jobs_source_id_fkey', 'scrape_jobs', type_='foreignkey')
    op.drop_constraint('scrape_jobs_data_revision_id_fkey', 'scrape_jobs', type_='foreignkey')
    op.drop_constraint('tickets_source_id_fkey', 'tickets', type_='foreignkey')
    op.drop_constraint('tickets_data_revision_id_fkey', 'tickets', type_='foreignkey')
    op.drop_constraint('revision_notifications_revision_id_fkey', 'revision_notifications', type_='foreignkey')
    
    op.create_foreign_key('change_diff_new_revision_id_fkey', 'change_diff', 'data_revisions', ['new_revision_id'], ['id'])
    op.create_foreign_key('change_diff_old_revision_id_fkey', 'change_diff', 'data_revisions', ['old_revision_id'], ['id'])
    op.create_foreign_key('data_revisions_source_id_fkey', 'data_revisions', 'sources', ['source_id'], ['id'])
    op.create_foreign_key('scrape_jobs_source_id_fkey', 'scrape_jobs', 'sources', ['source_id'], ['id'])
    op.create_foreign_key('scrape_jobs_data_revision_id_fkey', 'scrape_jobs', 'data_revisions', ['data_revision_id'], ['id'])
    op.create_foreign_key('tickets_source_id_fkey', 'tickets', 'sources', ['source_id'], ['id'])
    op.create_foreign_key('tickets_data_revision_id_fkey', 'tickets', 'data_revisions', ['data_revision_id'], ['id'])
    op.create_foreign_key('revision_notifications_revision_id_fkey', 'revision_notifications', 'data_revisions', ['revision_id'], ['id'])    
