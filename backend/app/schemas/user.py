from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique login username")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Minimum 6 character password")
    role: Optional[str] = Field("Viewer", description="Initial user role (Admin, Manager, Analyst, Viewer)")

class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str
