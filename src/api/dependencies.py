"""
API dependencies for FastAPI endpoints.
Provides helper functions for dependency injection in API routes.
"""
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

# Updated imports to use new structure
from ..db.session import get_db
# Assuming repositories might be refactored or removed if CRUD is used directly
# from src.persistence.repositories import AASShellRepository, AASSubmodelRepository 
from ..auth import models as auth_models, security
from ..db.crud import crud_user
from ..db.models import user as db_models
# from src.security.rbac import require_permission, require_role, RBACService, get_rbac_service # RBAC might need reimplementation or integration
from ..services.dpp_service import DPPService

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") # Adjust tokenUrl based on final API structure

# --- Database and Service Dependencies --- 

# def get_shell_repository(db: Session = Depends(get_db)) -> AASShellRepository:
#     return AASShellRepository(db)

# def get_submodel_repository(db: Session = Depends(get_db)) -> AASSubmodelRepository:
#     return AASSubmodelRepository(db)

# def get_dpp_service(
#     db: Session = Depends(get_db),
#     # shell_repo: AASShellRepository = Depends(get_shell_repository),
#     # submodel_repo: AASSubmodelRepository = Depends(get_submodel_repository)
# ) -> DPPService:
#     # This service might need refactoring based on new structure
#     # return DPPService(db, shell_repo, submodel_repo)
#     pass # Placeholder

# --- Authentication Dependencies --- 

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> Optional[db_models.User]:
    """
    Dependency to get the current user from the JWT token.
    Returns the user DB model or raises HTTPException if invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = security.decode_access_token(token)
    if token_data is None or token_data.username is None:
        raise credentials_exception
    user = crud_user.get_user_by_email(db, email=token_data.username)
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: db_models.User = Depends(get_current_user)) -> db_models.User:
    """
    Dependency to get the current *active* user.
    Raises HTTPException if the user is inactive.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

def get_current_active_superuser(current_user: db_models.User = Depends(get_current_active_user)) -> db_models.User:
    """
    Dependency to get the current active superuser.
    Raises HTTPException if the user is not a superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges"
        )
    return current_user

# TODO: Re-implement RBAC dependencies if needed, using the new User model
# def require_permission(permission: str):
#     def dependency(current_user: db_models.User = Depends(get_current_active_user)):
#         # Add logic to check user roles/permissions against the required permission
#         # This might involve fetching roles/permissions associated with the user
#         if permission not in get_user_permissions(current_user): # Placeholder function
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail=f"Requires permission: {permission}"
#             )
#         return current_user
#     return dependency

# Placeholder for getting user permissions - needs implementation
# def get_user_permissions(user: db_models.User) -> List[str]:
#    # Fetch permissions based on user roles or direct assignments
#    return ["read:public"] # Example

# --- Common Permission Dependencies (Example Placeholders) --- 

# def require_read_all_permission(user: db_models.User = Depends(require_permission("read:all"))):
#     return user

# def require_write_all_permission(user: db_models.User = Depends(require_permission("write:all"))):
#     return user

