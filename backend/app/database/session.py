from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from sqlalchemy.orm import Session


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)