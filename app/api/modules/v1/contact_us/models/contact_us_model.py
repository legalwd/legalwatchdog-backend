import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class ContactUs(SQLModel, table=True):
    __tablename__ = "contact_us"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    full_name: str = Field(max_length=255, nullable=False)
    email: str = Field(max_length=255, nullable=False, index=True)
    phone_number: str = Field(max_length=20, nullable=False)
    message: str = Field(max_length=1000, nullable=False)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
