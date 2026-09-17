from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, example="staff_ravi")
    email: str = Field(..., example="ravi@cafe.in")
    password: str = Field(..., min_length=6, example="securepass123")
    role: Optional[str] = Field("staff", example="staff")


class LoginRequest(BaseModel):
    username: str = Field(..., example="staff_ravi")
    password: str = Field(..., example="securepass123")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 28800  # 8 hours in seconds
    username: str
    role: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    created_at: str
