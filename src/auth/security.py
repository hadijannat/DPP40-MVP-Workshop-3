"""
Core security functions for password hashing and JWT handling.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError

# --- Configuration --- 

# Load from environment variables or a config file in a real application
# For now, using hardcoded defaults (replace with secure handling)
SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_for_jwt_should_be_long_and_random")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

# Password Hashing Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Token Data Model --- 

class TokenData(BaseModel):
    username: Optional[str] = None
    # Add other relevant claims like user ID, roles, etc.

# --- Password Hashing --- 

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

# --- JWT Handling --- 

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[TokenData]:
    """Decodes a JWT access token and validates its claims."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub") # Assuming username is stored in 'sub' claim
        if username is None:
            # Could raise specific credential exception here
            return None 
        # Validate expiration
        expire_timestamp = payload.get("exp")
        if expire_timestamp is None or datetime.now(timezone.utc) > datetime.fromtimestamp(expire_timestamp, timezone.utc):
             # Could raise specific credential exception for expired token
            return None
        
        # Use Pydantic model for potential future claim validation
        token_data = TokenData(username=username)
        return token_data
    except JWTError:
        # Could raise specific credential exception for invalid token
        return None
    except ValidationError:
        # Could raise specific credential exception for invalid claims
        return None


