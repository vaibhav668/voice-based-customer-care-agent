from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
)
from app.database.models.user import User
from app.exceptions.common import (
    UnauthorizedException,
)
from app.repositories.user_repository import UserRepository
from app.exceptions.common import ConflictException


class AuthService:

    def __init__(self, repository: UserRepository):
        self.repository = repository

    def register(self, request: RegisterRequest):

        if self.repository.get_by_email(request.email):
            raise ConflictException("Email already registered")

        if self.repository.get_by_phone(request.phone):
            raise ConflictException("Phone number already registered")

        user = User(
            full_name=request.full_name,
            email=request.email,
            phone=request.phone,
            password_hash=hash_password(request.password),
            preferred_language=getattr(request, "preferred_language", "en") or "en",
        )

        return self.repository.create(user)

    def login(self, request: LoginRequest):

        user = self.repository.get_by_email(
            request.email
        )

        if not user:
            raise UnauthorizedException()

        if not verify_password(
            request.password,
            user.password_hash,
        ):
            raise UnauthorizedException()

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
        }