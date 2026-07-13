import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load env variables from .env
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

def trigger_call(to_phone: str):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")
    public_url = os.getenv("PUBLIC_URL")

    if not all([account_sid, auth_token, from_phone, public_url]):
        print("[ERROR] Missing required Twilio settings in .env!")
        print("Please verify TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, and PUBLIC_URL are defined.")
        sys.exit(1)

    print("==============================================")
    print("INITIATING OUTBOUND TEST CALL TO CUSTOMER")
    print("==============================================")
    print(f"From: {from_phone}")
    print(f"To: {to_phone}")
    print(f"TwiML Webhook URL: {public_url}/api/v1/telephony/twilio/incoming")

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        call = client.calls.create(
            to=to_phone,
            from_=from_phone,
            url=f"{public_url}/api/v1/telephony/twilio/incoming"
        )
        print("\n[SUCCESS] Outbound call placed successfully!")
        print(f"Call SID: {call.sid}")
        print("Please pick up your phone when it rings to test the IVR + Agent flow.")
        print("==============================================")
    except Exception as e:
        print(f"\n[ERROR] Failed to place outbound call: {e}")
        sys.exit(1)

if __name__ == "__main__":
    to_number = "+918266894170"
    if len(sys.argv) > 1:
        to_number = sys.argv[1]
    trigger_call(to_number)
