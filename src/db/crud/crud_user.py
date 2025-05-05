"""
CRUD operations for the User model.
"""

from typing import Optional

from sqlalchemy.orm import Session

from ..auth import models as auth_models, security
from ..db.models import user as db_models

def get_user(db: Session, user_id: int) -> Optional[db_models.User]:
    """Get a user by their ID."""
    return db.query(db_models.User).filter(db_models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[db_models.User]:
    """Get a user by their email address."""
    return db.query(db_models.User).filter(db_models.User.email == email).first()

def create_user(db: Session, user: auth_models.UserCreate) -> db_models.User:
    """Create a new user in the database."""
    hashed_password = security.get_password_hash(user.password)
    db_user = db_models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, db_user: db_models.User, user_in: auth_models.UserUpdate) -> db_models.User:
    """Update an existing user."""
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        hashed_password = security.get_password_hash(update_data["password"])
        update_data["hashed_password"] = hashed_password
        del update_data["password"]
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
        
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Optional: Implement delete or deactivate user function if needed
# def delete_user(db: Session, user_id: int) -> Optional[db_models.User]:
#     db_user = get_user(db, user_id)
#     if db_user:
#         db.delete(db_user)
#         db.commit()
#     return db_user


