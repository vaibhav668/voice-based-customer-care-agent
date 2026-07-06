import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.scalar(stmt)

    def get_by_id(self, user_id):
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                pass
        stmt = select(User).where(User.id == user_id)
        return self.db.scalar(stmt)

    def get_by_phone(self, phone: str):
        stmt = select(User).where(User.phone == phone)
        return self.db.scalar(stmt)

    def update_language(self, user_id: str, language: str) -> User | None:
        user = self.get_by_id(user_id)
        if user:
            user.preferred_language = language
            self.db.commit()
            self.db.refresh(user)
        return user