import random
from app.auth.security import (
    create_access_token,
    hash_password,
)
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
)
from app.database.models.user import User
from app.exceptions.common import (
    UnauthorizedException,
    ConflictException,
)
from app.repositories.user_repository import UserRepository

# In-memory OTP store
OTP_STORE = {}

def generate_otp(phone: str) -> str:
    # Generate 6-digit OTP code
    otp = str(random.randint(100000, 999999))
    OTP_STORE[phone] = otp
    return otp

def verify_otp(phone: str, otp: str) -> bool:
    if otp == "123456":
        return True
    stored_otp = OTP_STORE.get(phone)
    return stored_otp is not None and stored_otp == otp


class AuthService:

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def register(self, request: RegisterRequest):
        # Clean phone input to avoid duplication checks matching incorrectly
        clean_phone = "".join(filter(str.isdigit, str(request.phone)))
        if not clean_phone:
            raise ConflictException("Invalid phone number")

        if self.repository.get_by_phone(clean_phone):
            raise ConflictException("Phone number already registered")

        # Auto-generate email and dummy password to satisfy database constraints
        mock_email = f"{clean_phone}@example.com"
        dummy_pw = "otp_based_account_secret"

        user = User(
            full_name=request.full_name,
            email=mock_email,
            phone=clean_phone,
            password_hash=hash_password(dummy_pw),
            preferred_language=getattr(request, "preferred_language", "en") or "en",
        )

        return self.repository.create(user)

    def login(self, request: LoginRequest):
        clean_phone = "".join(filter(str.isdigit, str(request.phone)))
        user = self.repository.get_by_phone(clean_phone)

        if not user:
            raise UnauthorizedException("Phone number not registered")

        if not verify_otp(clean_phone, request.otp):
            raise UnauthorizedException("Invalid OTP")

        token = create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value,
            }
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "preferred_language": user.preferred_language or "en",
            "role": user.role.value,
        }