from pydantic import BaseModel


class GoogleIDToken(BaseModel):
    id_token: str

class TokenResponse(BaseModel):
    access_token: str
    expires_at: int  # Unix timestamp


class RefreshTokenRequest(BaseModel):
    token: str