import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from dotenv import load_dotenv
from typing import Generator

# Load environment variables
load_dotenv()

# Database configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "codeanalysis")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "secret")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "codeanalysis")

# Export variables for use in other modules
__all__ = ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE', 'DATABASE_URL', 'get_db', 'init_db']

# Construct database URL
DATABASE_URL = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create sessionmaker
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

def get_db() -> Generator[Session, None, None]:
    """Get database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Initialize database tables."""
    from .models import Base
    Base.metadata.create_all(bind=engine)

def check_db_connection() -> bool:
    """Check if database connection is working."""
    try:
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return False
