"""add demo_request table

Revision ID: c7f2e4b6a9d0
Revises: 09d460509b3b
Create Date: 2026-01-27 14:15:00.000000

"""
from typing import Sequence, Union

import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7f2e4b6a9d0"
down_revision: Union[str, Sequence[str], None] = "09d460509b3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema by creating demo_requests table."""
    op.create_table(
        "demo_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("last_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("company_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("company_size", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("industry", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("company_website_url", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column("country", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("work_email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("job_title", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("additional_context", sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_demo_requests_id"), "demo_requests", ["id"], unique=False)
    op.create_index(
        op.f("ix_demo_requests_work_email"),
        "demo_requests",
        ["work_email"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema by dropping demo_requests table."""
    op.drop_index(op.f("ix_demo_requests_work_email"), table_name="demo_requests")
    op.drop_index(op.f("ix_demo_requests_id"), table_name="demo_requests")
    op.drop_table("demo_requests")
