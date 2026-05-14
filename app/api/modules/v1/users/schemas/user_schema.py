from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role_id: UUID
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
