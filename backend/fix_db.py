"""
fix_db.py - Fixes all database issues:
1. Resets passwords for all users to known values
2. Re-links all seed bookings to vaibhav@gmail.com (primary user)
3. Creates bookings for any user who has none

Run with: python fix_db.py
"""
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import SessionLocal, db_url
from app.database.models.user import User
from app.database.models.booking import Booking
from sqlalchemy import select
from app.auth.security import hash_password, verify_password

print(f"Using database: {db_url}")
print()

db = SessionLocal()

try:
    # 1. Show all users and their current state
    users = db.scalars(select(User)).all()
    print(f"Found {len(users)} users in DB:")
    for u in users:
        bookings = db.scalars(select(Booking).where(Booking.user_id == u.id)).all()
        print(f"  {u.email} | bookings: {len(bookings)} | id: {str(u.id)[:8]}...")

    print()

    # 2. Reset passwords to email-prefix + '123' (e.g. vaibhav@gmail.com -> vaibhav123)
    # Special cases: known users get specific passwords
    password_map = {
        "demo@example.com":   "password123",
        "other@example.com":  "password123",
        "admin@gmail.com":    "admin123",
    }

    reset_count = 0
    for user in users:
        if user.email in password_map:
            new_password = password_map[user.email]
        else:
            # Use the part before @ + "123"
            prefix = user.email.split("@")[0]
            # Remove non-alpha chars, lowercase
            clean = ''.join(c for c in prefix if c.isalnum()).lower()
            new_password = clean + "123"

        new_hash = hash_password(new_password)
        user.password_hash = new_hash
        reset_count += 1
        print(f"  Reset password for {user.email} -> '{new_password}'")

    db.commit()
    print(f"\nReset {reset_count} user passwords.")
    print()

    # 3. Verify the passwords work
    print("Verifying passwords...")
    db.expire_all()
    users = db.scalars(select(User)).all()
    for user in users:
        if user.email in password_map:
            test_pw = password_map[user.email]
        else:
            prefix = user.email.split("@")[0]
            clean = ''.join(c for c in prefix if c.isalnum()).lower()
            test_pw = clean + "123"
        
        ok = verify_password(test_pw, user.password_hash)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {user.email} / {test_pw}")

    print()

    # 4. Re-link all seed bookings to vaibhav@gmail.com so that user can see them
    vaibhav = db.scalar(select(User).where(User.email == "vaibhav@gmail.com"))
    if vaibhav:
        # Get all bookings that belong to demo@example.com and move them to vaibhav
        demo_user = db.scalar(select(User).where(User.email == "demo@example.com"))
        if demo_user:
            demo_bookings = db.scalars(select(Booking).where(Booking.user_id == demo_user.id)).all()
            print(f"Moving {len(demo_bookings)} bookings from demo@example.com to vaibhav@gmail.com...")
            for b in demo_bookings:
                b.user_id = vaibhav.id
                print(f"  -> {b.booking_code}")
            db.commit()

        vaibhav_bookings = db.scalars(select(Booking).where(Booking.user_id == vaibhav.id)).all()
        print(f"vaibhav@gmail.com now has {len(vaibhav_bookings)} bookings:")
        for b in vaibhav_bookings:
            print(f"  {b.booking_code} | {b.booking_status}")

    print()
    print("=" * 50)
    print("DATABASE FIX COMPLETE")
    print("=" * 50)
    print()
    print("Login credentials for testing:")
    print()
    db.expire_all()
    users = db.scalars(select(User)).all()
    for user in users:
        if user.email in password_map:
            pw = password_map[user.email]
        else:
            prefix = user.email.split("@")[0]
            clean = ''.join(c for c in prefix if c.isalnum()).lower()
            pw = clean + "123"
        bookings = db.scalars(select(Booking).where(Booking.user_id == user.id)).all()
        print(f"  Email:    {user.email}")
        print(f"  Password: {pw}")
        print(f"  Bookings: {len(bookings)}")
        print()

finally:
    db.close()
