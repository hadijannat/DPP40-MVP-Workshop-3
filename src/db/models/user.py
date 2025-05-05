"""
SQLAlchemy database models.
"""

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import declarative_base

# Use the new way to declare base for SQLAlchemy 2.0+
# from sqlalchemy.orm import DeclarativeBase
# class Base(DeclarativeBase):
#     pass
# For compatibility with potentially older setups or examples, using legacy base
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)


