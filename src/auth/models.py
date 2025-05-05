"""
Pydantic models for user data and authentication.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field

# --- User Models --- 

class UserBase(BaseModel):
    email: EmailStr = Field(..., description="User's email address (used as username)")
    full_name: Optional[str] = Field(None, description="User's full name")
    is_active: bool = Field(True, description="Whether the user account is active")
    is_superuser: bool = Field(False, description="Whether the user has superuser privileges")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="User's password (will be hashed)")

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserInDBBase(UserBase):
    id: int = Field(..., description="Unique user ID")

    model_config = {
        "from_attributes": True # Allow creating from ORM models
    }

# Stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str = Field(..., description="Hashed password")

# Returned by API (excluding password)
class User(UserInDBBase):
    pass

# --- Token Models --- 

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None # Subject (usually username/email)
    # Add other claims as needed


