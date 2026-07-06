from sqlalchemy.orm import Session

from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.service import AuthService
from app.repositories.user_repository import UserRepository


class AuthController:

    def __init__(self, db: Session):
        repository = UserRepository(db)
        self.service = AuthService(repository)

    def register(self, request: RegisterRequest):
        return self.service.register(request)

    def login(self, request: LoginRequest):
        return self.service.login(request)