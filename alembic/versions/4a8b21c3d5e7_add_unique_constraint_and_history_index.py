"""add_unique_constraint_and_history_index

Revision ID: 4a8b21c3d5e7
Revises: 3c5516098763
Create Date: 2026-02-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "4a8b21c3d5e7"
down_revision: Union[str, Sequence[str], None] = "3c5516098763"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_jurisdiction_field",
        "jurisdiction_states",
        ["jurisdiction_id", "field_key"],
    )
    op.create_index(
        "ix_jurisdiction_state_history_changed_at",
        "jurisdiction_state_history",
        ["changed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jurisdiction_state_history_changed_at",
        table_name="jurisdiction_state_history",
    )
    op.drop_constraint(
        "uq_jurisdiction_field",
        "jurisdiction_states",
        type_="unique",
    )
