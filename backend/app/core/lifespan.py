from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


from sqlalchemy import inspect, text
from app.database.session import engine


@asynccontextmanager
async def lifespan(app):
    logger.info("🚀 SupportAI Backend Started")
    try:
        with engine.begin() as conn:
            inspector = inspect(conn)
            if "users" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("users")]
                if "preferred_language" not in columns:
                    logger.info("Adding missing preferred_language column to users table...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN preferred_language VARCHAR(10) DEFAULT 'en'"))
    except Exception as e:
        logger.warning(f"Database column sync warning: {e}")
    yield
    logger.info("🛑 SupportAI Backend Stopped")