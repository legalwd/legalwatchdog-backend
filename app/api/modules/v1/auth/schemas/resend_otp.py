from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ResendOTPRequest(BaseModel):
    """
    Request model for resending a registration OTP.

    Attributes:
        email: User's email address used during registration.
    """

    email: EmailStr = Field(..., description="User's email address")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "admin@techcorp.com",
            }
        }
    )
