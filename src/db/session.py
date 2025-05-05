"""
Database session management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load from environment variables or config
# Example using PostgreSQL - adjust if using SQLite or other DB
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dpp_db") 
# Replace with actual connection string from config or env

# Create engine based on DATABASE_URL
# For SQLite: SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
# engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
# For PostgreSQL:
engine = create_engine(DATABASE_URL)

# Create session local
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create tables (optional, can be handled by Alembic)
# from .models.user import Base # Import Base from your models
# def init_db():
#     Base.metadata.create_all(bind=engine)


