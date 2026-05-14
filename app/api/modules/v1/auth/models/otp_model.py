import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Field, SQLModel


class OTP(SQLModel, table=True):
    __tablename__ = "otps"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    code: str = Field(max_length=6, nullable=False, index=True)
    expires_at: datetime = Field(nullable=False)
    is_used: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    @staticmethod
    def generate_code() -> str:
        from random import randint

        return f"{randint(100000, 999999)}"

    @staticmethod
    def expiry_time(minutes: int = 10) -> datetime:
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)
