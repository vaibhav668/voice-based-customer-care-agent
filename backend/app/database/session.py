import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config.settings import settings

db_url = settings.database_url

# Standardize postgres protocol scheme for SQLAlchemy compatibility
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Resolve relative SQLite paths to absolute paths so the same DB file is used
# regardless of which directory uvicorn is started from.
elif db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    if not os.path.isabs(db_path) and not db_path.startswith("\\") and not db_path.startswith("/"):
        backend_dir = Path(__file__).parent.parent.parent.resolve()
        resolved_path = (backend_dir / db_path).resolve()
        db_url = f"sqlite:///{resolved_path}"

engine = create_engine(
    db_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
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