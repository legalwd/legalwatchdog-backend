"""add_superadmin_and_activity_tracking_to_users

Revision ID: 13914474515e
Revises: 10bfbf0383bb
Create Date: 2025-12-18 23:08:30.118223

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '13914474515e'
down_revision: Union[str, Sequence[str], None] = '10bfbf0383bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add superadmin and activity tracking fields to users table
    op.add_column('users', sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('last_login', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('last_active', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_users_is_superadmin'), 'users', ['is_superadmin'], unique=False)
    op.create_index(op.f('ix_users_last_active'), 'users', ['last_active'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove superadmin and activity tracking fields from users table
    op.drop_index(op.f('ix_users_last_active'), table_name='users')
    op.drop_index(op.f('ix_users_is_superadmin'), table_name='users')
    op.drop_column('users', 'last_active')
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'is_superadmin')
