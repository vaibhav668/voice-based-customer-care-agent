import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load env variables from .env
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

def trigger_call(to_phone: str):
    auth_id = os.getenv("PLIVO_AUTH_ID")
    auth_token = os.getenv("PLIVO_AUTH_TOKEN")
    from_phone = os.getenv("PLIVO_PHONE_NUMBER")
    public_url = os.getenv("PUBLIC_URL")

    if not all([auth_id, auth_token, from_phone, public_url]):
        print("[ERROR] Missing required Plivo settings in .env!")
        print("Please verify PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PLIVO_PHONE_NUMBER, and PUBLIC_URL are defined.")
        sys.exit(1)

    print("==============================================")
    print("INITIATING OUTBOUND TEST CALL TO CUSTOMER")
    print("==============================================")
    print(f"From: {from_phone}")
    print(f"To: {to_phone}")
    print(f"Plivo Webhook URL: {public_url}/api/v1/telephony/plivo/incoming")

    try:
        import plivo
        client = plivo.RestClient(auth_id, auth_token)
        call = client.calls.create(
            to=to_phone,
            from_=from_phone,
            answer_url=f"{public_url}/api/v1/telephony/plivo/incoming",
            hangup_url=f"{public_url}/api/v1/telephony/plivo/hangup",
            ring_url=f"{public_url}/api/v1/telephony/plivo/events"
        )
        call_uuid = getattr(call, "call_uuid", None) or (call.get("call_uuid") if hasattr(call, "get") else None)
        print("\n[SUCCESS] Outbound call placed successfully!")
        print(f"Call UUID: {call_uuid}")
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
