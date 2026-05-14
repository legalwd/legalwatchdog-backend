"""Add full-text search to data_revision table

Revision ID: fts_data_revision
Revises: a8109c8c21c0
Create Date: 2025-11-21

Alembic migration for DATA_REVISION table with TSVECTOR and trigger.
"""
import os

revision = 'fts_data_revision'
down_revision = 'a8109c8c21c0'
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Add search_vector column to existing data_revisions table
    op.add_column('data_revisions', sa.Column('search_vector', postgresql.TSVECTOR, nullable=True))
    
    # Create GIN index for full-text search
    op.create_index('idx_data_revisions_search_vector', 'data_revisions', ['search_vector'], postgresql_using='gin')

    # Add trigger for search_vector auto-update
    sql_file_path = os.path.join(os.path.dirname(__file__), 'trigger_update_data_revision_search_vector.sql')
    with open(sql_file_path) as f:
        op.execute(f.read())


def downgrade():
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS trg_update_data_revisions_search_vector ON data_revisions;')
    op.execute('DROP FUNCTION IF EXISTS update_data_revisions_search_vector CASCADE;')
    
    # Drop index and column
    op.drop_index('idx_data_revisions_search_vector', table_name='data_revisions')
    op.drop_column('data_revisions', 'search_vector')
