from pydantic import BaseModel, EmailStr, Field, field_validator

from app.api.utils.validators import is_strong_password


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")


class PasswordResetVerify(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Reset code cannot be empty")
        if not v.isdigit():
            raise ValueError("Reset code must contain only digits")
        if len(v) != 6:
            raise ValueError("Reset code must be exactly 6 digits")
        return v


class PasswordResetConfirm(BaseModel):
    reset_token: str = Field(..., description="Temporary reset token from verify step")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v):
        error = is_strong_password(v)
        if error:
            raise ValueError(error)
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        """
        Validate that confirm_password matches new_password
        """
        new_password = info.data.get("new_password")
        if new_password != v:
            raise ValueError("Passwords do not match.")
        return v
