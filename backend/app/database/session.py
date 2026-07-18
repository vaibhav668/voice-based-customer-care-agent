import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

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
        if settings.app_env.lower() == "production":
            raise RuntimeError(
                "PostgreSQL connection failed in production; refusing to fall back to SQLite."
            ) from e
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
        poolclass=NullPool,
    )
    
    # Enable WAL mode for SQLite to support concurrent reads and writes
    if db_url.startswith("sqlite") or "sqlite" in db_url:
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            import sqlite3
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.close()

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
