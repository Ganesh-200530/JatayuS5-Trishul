from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., max_length=200)
    role: str = "reviewer"


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    totp_enabled: bool = False

    model_config = {"from_attributes": True}


class TOTPSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    message: str = "Scan the QR code with your authenticator app, then verify with a code."


class TOTPVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)
