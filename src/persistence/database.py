from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from typing import Generator
import os
import logging

from src.core.config import settings

# Configure logger
logger = logging.getLogger(__name__)

# Determine if we should use SQLite instead of PostgreSQL
USE_SQLITE = os.environ.get("USE_SQLITE", "True").lower() in ("true", "1", "t")

# Database URL
if USE_SQLITE:
    # SQLite for development/testing
    SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "dpp40_mvp.db")
    DATABASE_URL = f"sqlite:///{SQLITE_DB_PATH}"
    logger.info(f"Using SQLite database at {SQLITE_DB_PATH}")
else:
    # PostgreSQL for production
    DATABASE_URL = settings.DATABASE_URL
    logger.info(f"Using PostgreSQL database at {settings.DB_HOST}:{settings.DB_PORT}")

# Create SQLAlchemy engine
try:
    engine = create_engine(
        DATABASE_URL,
        echo=settings.DEBUG,  # Log SQL queries when in debug mode
        pool_pre_ping=True,   # Verify connection before use (helps with stale connections)
        connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    )
    
    # For SQLite, enable foreign key constraints
    if DATABASE_URL.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            
    logger.info("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# Create sessionmaker for creating sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db() -> Generator[Session, None, None]:
    """
    Create a new database session and close it when done.
    
    Yields:
        Session: An active SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """
    Initialize the database with all models.
    Creates tables if they don't exist.
    """
    try:
        # Import models to register them with Base
        from src.persistence import models  # noqa
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def check_db_connection() -> bool:
    """
    Check if the database connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        # Try to connect and execute a simple query
        with engine.connect() as conn:
            # SQLAlchemy 2.0 syntax
            conn.execute(text("SELECT 1"))
            conn.commit()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return False
