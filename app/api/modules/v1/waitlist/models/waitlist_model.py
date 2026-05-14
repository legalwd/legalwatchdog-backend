from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class Waitlist(SQLModel, table=True):
    __tablename__ = "waitlist"
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_email: str = Field(unique=True, index=True, max_length=255)
    organization_name: str = Field(index=True, max_length=255)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
