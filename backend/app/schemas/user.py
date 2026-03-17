from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=100)


class UserResponse(BaseModel):
    """Schema for user in responses."""

    id: int
    username: str
    email: str
    is_demo: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Auth response payload for login and refresh."""

    csrf_token: str  # returned in body for cross-domain clients (see ADR-001)
    token_type: str = "bearer"


class CsrfTokenResponse(BaseModel):
    """Response payload for CSRF token helper endpoint."""

    csrf_token: str


class RefreshRequest(BaseModel):
    """Request body for POST /api/auth/refresh and /api/auth/logout."""

    refresh_token: str
