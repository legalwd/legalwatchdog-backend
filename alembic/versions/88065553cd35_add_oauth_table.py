"""add oauth_table

Revision ID: 88065553cd35
Revises: 84a91f4f3ead
Create Date: 2025-11-29 10:23:59.708519

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '88065553cd35'
down_revision: Union[str, Sequence[str], None] = '84a91f4f3ead'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create OAuth audit table with IF NOT EXISTS to handle production conflicts
    op.execute("""
        CREATE TABLE IF NOT EXISTS oauth_login_events (
            id UUID NOT NULL,
            user_id UUID,
            provider VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL,
            failure_reason VARCHAR(500),
            error_code VARCHAR(100),
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            email VARCHAR(255),
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users (id)
        );
    """)
    
    # Create indexes only if they don't exist
    op.execute("CREATE INDEX IF NOT EXISTS ix_oauth_login_events_email ON oauth_login_events (email);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_oauth_login_events_id ON oauth_login_events (id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_oauth_login_events_timestamp ON oauth_login_events (timestamp);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_oauth_login_events_user_id ON oauth_login_events (user_id);")
    
    # Create refresh token metadata table with IF NOT EXISTS
    op.execute("""
        CREATE TABLE IF NOT EXISTS refresh_token_metadata (
            id UUID NOT NULL,
            user_id UUID NOT NULL,
            jti VARCHAR(255) NOT NULL,
            provider VARCHAR(50) NOT NULL,
            provider_token_exp BIGINT,
            ip_address VARCHAR(45),
            user_agent VARCHAR(500),
            expires_at TIMESTAMP WITH TIME ZONE,
            is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users (id)
        );
    """)
    
    # Create indexes for refresh_token_metadata
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_token_metadata_user_id ON refresh_token_metadata (user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_token_metadata_jti ON refresh_token_metadata (jti);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_token_metadata_is_revoked ON refresh_token_metadata (is_revoked);")
    
    # Add user profile columns with IF NOT EXISTS
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_url VARCHAR(500);")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_profile_data JSON;")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables if they exist
    op.execute("DROP TABLE IF EXISTS refresh_token_metadata;")
    op.execute("DROP TABLE IF EXISTS oauth_login_events;")
    
    # Remove user columns if they exist
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS provider_profile_data;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS profile_picture_url;")
