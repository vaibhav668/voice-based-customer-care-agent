import asyncio
import httpx
from app.database.session import SessionLocal
from app.database.models.user import User
from app.database.models.booking import Booking
from main import app

async def test_flow(phone_number, booking_code, language_digit):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        call_uuid = f"CA-Test-Flow-{phone_number}-{booking_code}"

        # 1. Incoming
        res1 = await client.post("/api/v1/telephony/plivo/incoming", data={"CallUUID": call_uuid, "From": phone_number})
        
        # 2. Language selection
        res2 = await client.post("/api/v1/telephony/plivo/language", data={"CallUUID": call_uuid, "Digits": language_digit})
        
        # 3. Verify booking reference code
        res3 = await client.post("/api/v1/telephony/plivo/verify_code", data={"CallUUID": call_uuid, "Digits": booking_code})
        print(f"\n=========================================")
        print(f"PHONE: {phone_number} | BOOKING: {booking_code} | LANG: {language_digit}")
        print(f"=========================================")
        print(res3.text)

async def main():
    # Test valid booking verification in English
    await test_flow("+918266894170", "1234", "1")
    # Test valid booking verification in Hindi
    await test_flow("+918266894170", "1234", "2")
    # Test unauthorized booking verification in English
    await test_flow("+918266894170", "9999", "1")
    # Test invalid booking code (not found) in English
    await test_flow("+918266894170", "0000", "1")

if __name__ == "__main__":
    asyncio.run(main())
