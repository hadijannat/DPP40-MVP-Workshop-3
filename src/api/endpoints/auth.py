"""
Authentication endpoints for DPP40 MVP.

This module provides endpoints for user authentication and token issuance.
"""
from datetime import timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# Updated imports
from ...auth import models as auth_models, security
from ...db.crud import crud_user
from ...db.session import get_db
from ...api import dependencies # Import dependencies to use get_current_active_user
from ...core.config import settings # Assuming settings are in core.config

# from src.utils.logging import get_logger # Assuming logger setup elsewhere or remove
# logger = get_logger(__name__)
logger = logging.getLogger(__name__) # Basic logger

# Create a router
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        422: {"description": "Validation Error"}
    }
)

logger.info("Initializing auth router")

@router.post(
    "/token",
    response_model=auth_models.Token,
    summary="Login for access token",
    description="Exchange username (email) and password for a JWT access token"
)
async def login_for_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Uses email as the username.
    """
    logger.info(f"Token requested for user: {form_data.username}")
    
    # Authenticate the user (using email as username)
    user = crud_user.get_user_by_email(db, email=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Authentication failed for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user.is_active:
        logger.warning(f"Authentication attempt from inactive user: {form_data.username}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    # Generate the JWT token
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email}, # Use email in the "sub" claim
        expires_delta=access_token_expires
    )
    
    logger.info(f"Token generated successfully for user: {user.email}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get(
    "/me",
    response_model=auth_models.User, # Use the User model (excludes password)
    summary="Get current user info",
    description="Get information about the currently authenticated user"
)
async def read_users_me(
    current_user: auth_models.User = Depends(dependencies.get_current_active_user) # Use the dependency
):
    """
    Get current user information based on the provided JWT token.
    """
    logger.info(f"User info requested for: {current_user.email}")
    # The dependency already returns the validated user model
    return current_user

# Optional: Add user creation/management endpoints if needed (likely restricted to superusers)
# @router.post("/users/", response_model=auth_models.User, status_code=status.HTTP_201_CREATED)
# def create_new_user(
#     *, 
#     db: Session = Depends(get_db),
#     user_in: auth_models.UserCreate,
#     # current_user: models.User = Depends(dependencies.get_current_active_superuser) # Protect endpoint
# ):
#     user = crud_user.get_user_by_email(db, email=user_in.email)
#     if user:
#         raise HTTPException(
#             status_code=400,
#             detail="The user with this email already exists in the system.",
#         )
#     user = crud_user.create_user(db=db, user=user_in)
#     return user

