import asyncio
import httpx
from app.database.session import SessionLocal
from app.database.models.user import User
from app.database.models.booking import Booking
from main import app

async def main():
    db = SessionLocal()
    # Let's find the user with phone '8266894170' (which we updated earlier)
    user = db.query(User).filter(User.phone.like('%8266894170%')).first()
    if not user:
        print("Test user not found in SQLite database!")
        db.close()
        return

    # Let's find their booking code
    booking = db.query(Booking).filter(Booking.user_id == user.id).first()
    if not booking:
        print("Test booking not found for this user!")
        db.close()
        return

    print(f"Testing with user phone: {user.phone}, booking code: {booking.booking_code}")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        call_uuid = "CA-Test-Vernacular-123456"

        # 1. Incoming Call
        print("\n--- 1. Incoming ---")
        res1 = await client.post("/api/v1/telephony/plivo/incoming", data={"CallUUID": call_uuid, "From": user.phone})
        print(res1.text)

        # 2. Language Selection -> Hindi (Digits=2)
        print("\n--- 2. Language Selection (Hindi) ---")
        res2 = await client.post("/api/v1/telephony/plivo/language", data={"CallUUID": call_uuid, "Digits": "2"})
        print(res2.text)

        # 3. Verify Code
        print("\n--- 3. Verify Code ---")
        res3 = await client.post("/api/v1/telephony/plivo/verify_code", data={"CallUUID": call_uuid, "Digits": booking.booking_code})
        print(res3.text)

    db.close()

if __name__ == "__main__":
    asyncio.run(main())
