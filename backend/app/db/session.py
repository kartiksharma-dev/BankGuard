import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load the project's root .env file.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Configure it in the project-root .env file."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    # Limit PostgreSQL connection establishment to 5 seconds.
    # psycopg v3 forwards connect_args to libpq as connection keyword arguments.
    # Without this, a non-responsive PostgreSQL host causes SQLAlchemy to block
    # for the OS-level TCP timeout (several minutes), hanging every API request.
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for BankGuard SQLAlchemy models."""
    pass


def get_db():
    """Provide a database session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()       