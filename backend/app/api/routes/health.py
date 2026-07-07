from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/health",
    tags=["Health"],
)


@router.get("/")
async def health_check(db: Session = Depends(get_db)):
    db_type = "unknown"
    try:
        db_type = db.bind.dialect.name
    except Exception as e:
        db_type = f"error: {e}"

    return success_response(
        data={
            "status": "healthy",
            "version": "1.0.0",
            "database": db_type
        }
    )