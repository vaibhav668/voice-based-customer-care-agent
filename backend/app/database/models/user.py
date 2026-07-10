import enum
import base64
from sqlalchemy import Boolean, Enum, String
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.database.base import Base
from app.database.mixins import TimestampMixin, UUIDMixin

# Symmetric field-level encryption helper functions
KEY = b"supersecretkey"

def encrypt_field(val: str) -> str:
    if not val:
        return val
    encoded = val.encode('utf-8')
    xored = bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(encoded))
    return base64.b64encode(xored).decode('utf-8')

def decrypt_field(val: str) -> str:
    if not val:
        return val
    try:
        xored = base64.b64decode(val.encode('utf-8'))
        decrypted = bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(xored))
        return decrypted.decode('utf-8')
    except Exception:
        return val


class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_field(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return decrypt_field(value)
        return value


class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    name_encrypted: Mapped[str] = mapped_column(
        EncryptedString(255),
        nullable=True,
    )

    @hybrid_property
    def full_name(self) -> str:
        return self.name_encrypted

    @full_name.setter
    def full_name(self, value: str):
        self.name_encrypted = value

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.CUSTOMER,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    preferred_language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
    )

    bookings = relationship(
    "Booking",
    back_populates="user",
    )