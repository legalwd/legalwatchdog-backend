import uuid
from typing import Dict, Optional

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ChangeDiff(SQLModel, table=True):
    __tablename__ = "change_diff"

    diff_id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    new_revision_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("data_revisions.id", ondelete="CASCADE"), nullable=False)
    )

    old_revision_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("data_revisions.id", ondelete="CASCADE"), nullable=False)
    )

    diff_patch: Optional[Dict] = Field(default=None, sa_column=Column(JSONB))

    ai_confidence: Optional[float] = Field(default=None)
