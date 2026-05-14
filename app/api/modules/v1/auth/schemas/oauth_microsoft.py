from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class MicrosoftAuthRequest(BaseModel):
    """Schema for initiating Microsoft OAuth flow."""

    redirect_uri: Optional[str] = Field(
        None, description="Optional custom redirect URI. Uses default if not provided."
    )


class MicrosoftAuthResponse(BaseModel):
    """Response containing authorization URL."""

    authorization_url: str = Field(..., description="URL to redirect user to Microsoft login")
    state: str = Field(..., description="State parameter for CSRF protection")


class MicrosoftCallbackRequest(BaseModel):
    """Schema for Microsoft OAuth callback."""

    code: str = Field(..., description="Authorization code from Microsoft")
    state: str = Field(..., description="State parameter for validation")


class MicrosoftUserInfo(BaseModel):
    """Microsoft user information from Graph API."""

    id: str
    email: EmailStr
    display_name: Optional[str] = Field(None, alias="displayName")
    given_name: Optional[str] = Field(None, alias="givenName")
    surname: Optional[str] = Field(None, alias="surname")
    user_principal_name: Optional[str] = Field(None, alias="userPrincipalName")


class MicrosoftAuthCompleteResponse(BaseModel):
    """Response after successful Microsoft authentication."""

    access_token: str
    user_id: str
    email: str
    organization_id: str
    is_new_user: bool
