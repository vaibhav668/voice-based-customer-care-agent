import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal
from app.database.models.user import User
from app.auth.service import verify_otp

db = SessionLocal()
try:
    print("Listing all registered users in database:")
    users = db.query(User).all()
    for u in users:
        print(f"ID: {u.id} | Name: {u.full_name} | Email: {u.email} | Phone: {u.phone} | Role: {u.role} | Active: {u.is_active}")

    print("\nTesting admin verification details:")
    admin_phone = "9990001112"
    admin_user = db.query(User).filter_by(phone=admin_phone).first()
    if admin_user:
        print(f"Admin user found! ID: {admin_user.id}, Role: {admin_user.role}")
        # Test OTP verification
        otp_val = "123456"
        valid = verify_otp(admin_phone, otp_val)
        print(f"Is OTP '{otp_val}' valid for admin phone '{admin_phone}': {valid}")
    else:
        print(f"Admin user with phone '{admin_phone}' NOT found!")

finally:
    db.close()
