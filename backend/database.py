"""
Database connection and session management for Scoring Basket
Handles SQLAlchemy engine and session creation
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator, Any
import os
from dotenv import load_dotenv
from pathlib import Path
from fastapi import Depends

# Load environment variables
ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/basketball.db")

# SQLite-specific configuration
if DATABASE_URL.startswith("sqlite"):
    # For SQLite, we need to enable foreign keys and use StaticPool for in-memory testing
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Enable foreign key support in SQLite"""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # For other databases (PostgreSQL, MySQL, etc.)
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=os.getenv("SQL_ECHO", "False").lower() == "true",
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Any:
    """
    Dependency for getting database session in FastAPI routes
    Usage: def my_route(db = Depends(get_db))
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Generator[Session, None, None]:
    """
    Alternative database dependency that returns a properly typed Session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Remove all type annotations to avoid Pydantic schema generation issues
get_db.__annotations__ = {}


@contextmanager
def get_db_context():
    """
    Context manager for database session outside of request context
    Usage:
        with get_db_context() as db:
            # use db
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - creates tables if they don't exist
    Called once at application startup
    """
    from .models import Base
    
    # For SQLite, check if tables already exist
    if DATABASE_URL.startswith("sqlite"):
        # Tables are created by schema.sql, not by Base.metadata.create_all()
        # But we keep this for flexibility during development
        pass
    else:
        # For other databases, create tables if needed
        Base.metadata.create_all(bind=engine)


def verify_db_connection() -> bool:
    """
    Verify database connection is working
    Returns True if connection is successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"Database connection error: {e}")
        return False
