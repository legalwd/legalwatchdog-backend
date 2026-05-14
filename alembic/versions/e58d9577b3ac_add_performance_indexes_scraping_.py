"""Add performance indexes for scraping and campaign queries.

Revision ID: e58d9577b3ac
Revises: 2e8f3a1b9c4d
Create Date: 2026-05-07 11:04:53.300410

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e58d9577b3ac"
down_revision: Union[str, Sequence[str], None] = "2e8f3a1b9c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_scrape_jobs_jurisdiction_job_status",
        "scrape_jobs",
        ["jurisdiction_scrape_job_id", "status"],
    )
    op.create_index(
        "ix_jurisdiction_scrape_jobs_jurisdiction_status_completed",
        "jurisdiction_scrape_jobs",
        ["jurisdiction_id", "status", "completed_at"],
    )
    op.create_index(
        "ix_jurisdictions_campaign_discovery",
        "jurisdictions",
        ["campaign_id", "discovery_status"],
    )
    op.create_index(
        "ix_jurisdictions_next_scrape_auto",
        "jurisdictions",
        ["next_scrape_time", "enable_auto_scrape", "is_deleted"],
    )
    op.create_index(
        "ix_sources_jurisdiction_active",
        "sources",
        ["jurisdiction_id", "is_active", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_sources_jurisdiction_active")
    op.drop_index("ix_jurisdictions_next_scrape_auto")
    op.drop_index("ix_jurisdictions_campaign_discovery")
    op.drop_index("ix_jurisdiction_scrape_jobs_jurisdiction_status_completed")
    op.drop_index("ix_scrape_jobs_jurisdiction_job_status")
