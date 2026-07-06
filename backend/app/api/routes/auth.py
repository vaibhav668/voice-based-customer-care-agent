from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.controllers.auth_controller import AuthController
from app.auth.schemas import LoginRequest, RegisterRequest
from app.database.session import get_db
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post("/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    controller = AuthController(db)

    user = controller.register(request)

    return success_response(
        data={
            "id": str(user.id),
            "email": user.email,
        },
        message="User registered successfully",
    )


@router.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    controller = AuthController(db)

    token = controller.login(request)

    return success_response(
        data=token,
        message="Login successful",
    )