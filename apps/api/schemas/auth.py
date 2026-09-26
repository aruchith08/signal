"""
Authentication Pydantic Schemas
"""
from typing import Optional
from pydantic import BaseModel, Field

from apps.api.schemas.user import UserRead


class UserRegister(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: Optional[str] = None
    role: str = Field(default="user", pattern="^(user|reviewer|admin)$")


class UserLogin(BaseModel):
    username: str = Field(..., description="Username or email address")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class TokenData(BaseModel):
    sub: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
