from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.controllers.auth_controller import AuthController
from app.auth.schemas import LoginRequest, RegisterRequest, SendOTPRequest
from app.auth.service import generate_otp
from app.database.session import get_db
from app.utils.response import success_response

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post("/send-otp")
def send_otp(
    request: SendOTPRequest,
):
    clean_phone = "".join(filter(str.isdigit, str(request.phone)))
    if len(clean_phone) > 10:
        clean_phone = clean_phone[-10:]
    otp = generate_otp(clean_phone)
    # Return OTP in payload to simplify local testing and debugging
    return success_response(
        data={
            "phone": clean_phone,
            "otp": otp,
        },
        message="OTP sent successfully (Simulated)",
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
            "phone": user.phone,
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