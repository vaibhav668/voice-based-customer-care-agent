import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config.settings import settings

db_url = settings.database_url

# Standardize postgres protocol scheme for SQLAlchemy compatibility
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Check connection and fallback to SQLite if postgres is unavailable
engine = None
if "postgresql" in db_url:
    try:
        # Create a temporary engine with short timeout to check connection
        temp_engine = create_engine(db_url, connect_args={"connect_timeout": 2})
        with temp_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine = temp_engine
        print("Connected to PostgreSQL successfully.")
    except Exception as e:
        sqlite_path = Path(__file__).parent.parent.parent / "supportai.db"
        print(f"Warning: PostgreSQL connection failed ({e}). Falling back to SQLite at {sqlite_path}")
        db_url = f"sqlite:///{sqlite_path}"

if engine is None:
    # Set up SQLite engine
    # Note: sqlite requires different connect_args for multithreading
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    engine = create_engine(
        db_url,
        echo=settings.debug,
        connect_args=connect_args,
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()