from typing import Optional

from pydantic import BaseModel


class AppleAuthRequest(BaseModel):
    code: str
    id_token: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    redirect_uri: Optional[str] = None
