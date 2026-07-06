from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

from sqlalchemy import inspect, text
from app.database.session import engine
from app.database.base import Base
import app.database.models  # Ensures all ORM models are registered with Base.metadata


@asynccontextmanager
async def lifespan(app):
    logger.info("🚀 SupportAI Backend Started")
    try:
        # Create all database tables automatically if missing
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")

        with engine.begin() as conn:
            inspector = inspect(conn)
            if "users" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("users")]
                if "preferred_language" not in columns:
                    logger.info("Adding missing preferred_language column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN preferred_language VARCHAR(10) DEFAULT 'en'"))
    except Exception as e:
        logger.warning(f"Database table/column sync warning: {e}")
    yield
    logger.info("🛑 SupportAI Backend Stopped")