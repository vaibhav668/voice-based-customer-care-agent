import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal
from app.database.models.booking import Booking
from app.database.models.user import User

db = SessionLocal()
try:
    booking = db.query(Booking).filter_by(booking_code="BK-1234").first()
    print("Booking code:", booking.booking_code)
    print("User ID:", booking.user_id)
    if booking.user:
        print("User Name:", booking.user.full_name)
        print("User Phone:", booking.user.phone)
        print("User Email:", booking.user.email)
    else:
        print("User relationship is None")
finally:
    db.close()
