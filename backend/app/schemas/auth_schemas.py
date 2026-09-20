"""
schemas/auth_schemas.py

WHAT THIS FILE DOES:
Pydantic request/response models for signup, login, and the returned
user object. FastAPI uses these to validate incoming JSON and to
serialize outgoing responses. Keeping schemas separate from SQLAlchemy
models (models/) is standard practice: it stops you from accidentally
returning sensitive fields like hashed_password to the client.
"""

import uuid
from pydantic import BaseModel, EmailStr, ConfigDict


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_superadmin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
