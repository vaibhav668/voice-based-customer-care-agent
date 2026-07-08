import sys
import os
import uuid

# Ensure backend root is on Python sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

# Manually load environment variables from .env file to avoid Pydantic settings missing errors
env_path = os.path.join(backend_dir, ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                os.environ[key] = val

from app.database.session import SessionLocal
from app.database.models.user import User, UserRole
from app.database.models.booking import Booking
from app.database.models.complaint import Complaint, ComplaintStatus
from app.auth.security import hash_password

def create_admin():
    db = SessionLocal()
    try:
        email = "admin@example.com"
        admin = db.query(User).filter_by(email=email).first()
        if not admin:
            admin = User(
                id=uuid.uuid4(),
                full_name="System Admin",
                email=email,
                phone="9990001112",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
                preferred_language="en"
            )
            db.add(admin)
            db.commit()
            print(f"Admin user created successfully with email: {email} and password: admin123")
        else:
            admin.role = UserRole.ADMIN
            admin.password_hash = hash_password("admin123")
            db.commit()
            print(f"Existing user {email} updated to ADMIN role and password reset to admin123")
            
        # Seed Complaint tickets if none exist
        complaint_count = db.query(Complaint).count()
        if complaint_count == 0:
            print("Seeding customer complaints (tickets)...")
            
            # Map booking codes to demo complaints
            complaint_seeds = [
                {
                    "booking_code": "BK-1234",
                    "code": "CMP-8412",
                    "title": "AC Vent Cleanliness Issue",
                    "desc": "AI detected high frustration. Switching to Empathy Model V2. AC vent was dusty and blowing low air on seat A12.",
                    "status": ComplaintStatus.OPEN
                },
                {
                    "booking_code": "BK-5678",
                    "code": "CMP-8409",
                    "title": "Trip Delay Compensation Query",
                    "desc": "Refund policy conflict resolved. AI offered tier-2 compensation. Delay of 25 minutes on Mumbai-Pune trip.",
                    "status": ComplaintStatus.IN_PROGRESS
                },
                {
                    "booking_code": "BK-2468",
                    "code": "CMP-8405",
                    "title": "Cancellation Refund Status",
                    "desc": "Complex billing technicality. Transferred to Senior Agent. Refund of cancellation is pending for 3 business days.",
                    "status": ComplaintStatus.OPEN
                }
            ]
            
            for seed in complaint_seeds:
                booking = db.query(Booking).filter_by(booking_code=seed["booking_code"]).first()
                if booking:
                    complaint = Complaint(
                        id=uuid.uuid4(),
                        complaint_code=seed["code"],
                        booking_id=booking.id,
                        title=seed["title"],
                        description=seed["desc"],
                        status=seed["status"]
                    )
                    db.add(complaint)
            db.commit()
            print("Successfully seeded 3 complaints (tickets) in the database.")
        else:
            print(f"Complaints database already seeded (count: {complaint_count}).")

    except Exception as e:
        print(f"Error creating admin/seeding complaints: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
