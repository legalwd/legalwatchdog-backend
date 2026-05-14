import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class VerifyOTPRequest(BaseModel):
    """
    Request model for OTP verification.

    Attributes:
        email: User's email address
        code: 6-digit OTP code sent to email
    """

    email: EmailStr = Field(..., description="User's email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "admin@techcorp.com", "code": "123456"}}
    )


class VerifyOTPResponse(BaseModel):
    """
    Response model for successful OTP verification.

    Attributes:
        organization_id: Created organization ID
        organization_name: Organization name
        email: User email
        user_id: Created user ID
    """

    organization_id: uuid.UUID
    organization_name: str
    email: EmailStr
    user_id: uuid.UUID

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "organization_id": "550e8400-e29b-41d4-a716-446655440000",
                "organization_name": "Tech Corp",
                "email": "admin@techcorp.com",
                "user_id": "660e8400-e29b-41d4-a716-446655440000",
            }
        }
    )
