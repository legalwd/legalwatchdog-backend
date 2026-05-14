"""add discovery status to jurisdictions

Revision ID: e1c4b9e6d2a1
Revises: 767c7c05f76a
Create Date: 2026-04-01 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1c4b9e6d2a1"
down_revision = "767c7c05f76a"
branch_labels = None
depends_on = None


discoverystatus_enum = sa.Enum(
    "PENDING",
    "DISCOVERED",
    "DISCOVERY_FAILED",
    "REQUIRES_MANUAL_SOURCES",
    name="discoverystatus",
)


def upgrade():
    bind = op.get_bind()
    discoverystatus_enum.create(bind, checkfirst=True)
    op.add_column(
        "jurisdictions",
        sa.Column(
            "discovery_status",
            discoverystatus_enum,
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.create_index(
        op.f("ix_jurisdictions_discovery_status"),
        "jurisdictions",
        ["discovery_status"],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()
    op.drop_index(op.f("ix_jurisdictions_discovery_status"), table_name="jurisdictions")
    op.drop_column("jurisdictions", "discovery_status")
    discoverystatus_enum.drop(bind, checkfirst=True)
