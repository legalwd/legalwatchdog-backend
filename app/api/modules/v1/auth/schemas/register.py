from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.api.utils.validators import is_company_email, is_strong_password


class RegisterRequest(BaseModel):
    name: str = Field(..., max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str
    token: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_must_be_company(cls, v):
        if not is_company_email(v):
            raise ValueError("Only company email addresses are allowed.")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        error = is_strong_password(v)
        if error:
            raise ValueError(error)
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, values):
        password = (
            values.data.get("password") if hasattr(values, "data") else values.get("password")
        )
        if password is not None and v != password:
            raise ValueError("Passwords do not match.")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class OTPVerifyResponse(BaseModel):
    message: str
    verified: bool
