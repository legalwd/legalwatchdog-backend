"""initiate comments model

Revision ID: 1f96ba14f37b
Revises: 7810240dba0c
Create Date: 2025-12-06 12:58:30.831716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1f96ba14f37b'
down_revision: Union[str, Sequence[str], None] = '7810240dba0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create comments table
    op.create_table('comments',
        sa.Column('comment_id', postgresql.UUID(), nullable=False),
        sa.Column('user_id', postgresql.UUID(), nullable=True),
        sa.Column('participant_id', postgresql.UUID(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('mentioned_user_ids', postgresql.JSONB(), nullable=True),
        sa.Column('mentioned_participant_ids', postgresql.JSONB(), nullable=True),
        sa.Column('ticket_id', postgresql.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['participant_id'], ['external_participants.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.PrimaryKeyConstraint('comment_id'),
        sa.CheckConstraint(
            '(user_id IS NOT NULL AND participant_id IS NULL) OR (user_id IS NULL AND participant_id IS NOT NULL)',
            name='ck_comment_author'
        )
    )
    
    # Create indexes
    op.create_index('ix_comments_user_created', 'comments', ['user_id', sa.text('created_at DESC')])
    op.create_index('ix_comments_participant_created', 'comments', ['participant_id', sa.text('created_at DESC')])
    op.create_index('ix_comments_ticket', 'comments', ['ticket_id'])
    op.create_index('ix_comments_active', 'comments', ['comment_id'], 
                   postgresql_where=sa.text('deleted_at IS NULL'))
    
    # Create GIN indexes for JSON arrays for faster lookups
    op.execute('CREATE INDEX ix_comments_mentioned_user_ids ON comments USING GIN (mentioned_user_ids)')
    op.execute('CREATE INDEX ix_comments_mentioned_participant_ids ON comments USING GIN (mentioned_participant_ids)')


def downgrade() -> None:
    # Drop GIN indexes
    op.execute('DROP INDEX IF EXISTS ix_comments_mentioned_participant_ids')
    op.execute('DROP INDEX IF EXISTS ix_comments_mentioned_user_ids')
    
    # Drop other indexes
    op.drop_index('ix_comments_active', table_name='comments')
    op.drop_index('ix_comments_ticket', table_name='comments')
    op.drop_index('ix_comments_participant_created', table_name='comments')
    op.drop_index('ix_comments_user_created', table_name='comments')
    
    # Drop comments table
    op.drop_table('comments')
