import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

import plivo

def test_plivo_sms():
    auth_id = os.getenv("PLIVO_AUTH_ID")
    auth_token = os.getenv("PLIVO_AUTH_TOKEN")
    from_phone = os.getenv("PLIVO_PHONE_NUMBER")
    
    # We will try to send SMS to the test customer phone (9876543210) and your custom destination if provided
    dest_phone = "+918266894170" # Default testing number from trigger script
    
    print(f"Auth ID: {auth_id}")
    print(f"From Phone: {from_phone}")
    print(f"Sending test SMS to: {dest_phone}...")
    
    try:
        client = plivo.RestClient(auth_id, auth_token)
        response = client.messages.create(
            src=from_phone,
            dst=dest_phone,
            text="SupportAI Verification OTP: 123456"
        )
        print("Plivo Response:")
        print(response)
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    test_plivo_sms()
