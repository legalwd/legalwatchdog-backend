"""remove ticket permissions from member role

Revision ID: a1b2c3d4e5f6
Revises: 25bc91239c2a
Create Date: 2026-01-07
"""

from typing import Sequence, Union
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "25bc91239c2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove ticket-related permissions from member role
    in both roles and role_templates.
    """

    # roles table
    op.execute("""
        UPDATE roles
        SET permissions =
            permissions
            - 'view_tickets'
            - 'create_tickets'
            - 'edit_tickets'
        WHERE name = 'Member';
    """)

    # role_templates table
    op.execute("""
        UPDATE role_templates
        SET permissions =
            permissions
            - 'view_tickets'
            - 'create_tickets'
            - 'edit_tickets'
        WHERE name = 'member';
    """)


def downgrade() -> None:
    """
    Restore ticket-related permissions to member role
    in both roles and role_templates.
    """

    # roles table
    op.execute("""
        UPDATE roles
        SET permissions = permissions || '{
            "view_tickets": true,
            "create_tickets": true,
            "edit_tickets": true
        }'::jsonb
        WHERE name = 'Member';
    """)

    # role_templates table
    op.execute("""
        UPDATE role_templates
        SET permissions = permissions || '{
            "view_tickets": true,
            "create_tickets": true,
            "edit_tickets": true
        }'::jsonb
        WHERE name = 'member';
    """)
