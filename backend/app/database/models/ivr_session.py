from sqlalchemy import Boolean, Column, String
from app.database.base import Base
from app.database.mixins import TimestampMixin


class IvrSession(TimestampMixin, Base):
    __tablename__ = "ivr_sessions"

    call_id = Column(String(64), primary_key=True, index=True)
    phone_number = Column(String(50), nullable=True)
    state = Column(String(50), nullable=False, default="INCOMING")
    recording_consent = Column(Boolean, nullable=True)
    language = Column(String(10), nullable=False, default="en")
    user_id = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=False)
    booking_code = Column(String(50), nullable=True)
