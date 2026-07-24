import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import SessionLocal
from app.database.models.user import User
from app.database.models.booking import Booking

db = SessionLocal()

print("--- USERS ---")
users = db.query(User).all()
for u in users:
    print(f"ID: {u.id} | Name: {u.full_name} | Phone: {u.phone} | Email: {u.email}")

print("\n--- BOOKINGS ---")
bookings = db.query(Booking).all()
for b in bookings:
    print(f"Code: {b.booking_code} | UserID: {b.user_id} | Seat: {b.seat_number} | Status: {b.booking_status.value} | Payment: {b.payment_status.value}")

db.close()
