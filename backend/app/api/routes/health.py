from fastapi import APIRouter

from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/health",
    tags=["Health"],
)


@router.get("/")
async def health_check():
    return success_response(
        data={"status": "healthy", "version": "1.0.0"}
    )