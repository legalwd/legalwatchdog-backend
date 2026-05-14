from typing import Dict, Optional

from pydantic import BaseModel, Field


class RoleCreateRequest(BaseModel):
    name: str = Field(..., max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    permissions: Dict[str, bool] = Field(default_factory=dict)


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    permissions: Dict[str, bool]


class UserRoleResponse(BaseModel):
    user_id: str
    role_id: str
    role_name: str
    permissions: Dict[str, bool]
