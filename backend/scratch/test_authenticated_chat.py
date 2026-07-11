import sys
import os
from pathlib import Path

# Setup paths to import from backend
_BASE_DIR = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(_BASE_DIR))

import urllib.request
import json
import ssl
from app.auth.security import create_access_token

# Real user ID of Vaibhav Pokhriyal
real_user_id = "78073333-23f0-4f06-9f3a-404fa6126dc4"
token = create_access_token({
    "sub": real_user_id,
    "email": "8266894170@example.com",
    "role": "CUSTOMER"
})
print("Generated Token:", token)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://voice-based-customer-care-agent-1.onrender.com/api/v1/chat/"
data = {
    "session_id": "test-session-auth-999",
    "message": "show my bookings",
    "language": "en"
}
payload = json.dumps(data).encode("utf-8")

req = urllib.request.Request(
    url,
    data=payload,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req, context=ctx) as response:
        html = response.read().decode("utf-8")
        print("STATUS:", response.status)
        print("RESPONSE:")
        print(html)
except urllib.error.HTTPError as e:
    print("HTTP ERROR CODE:", e.code)
    try:
        print("HTTP ERROR RESPONSE:")
        print(e.read().decode("utf-8"))
    except Exception as err:
        print("Read error:", err)
except Exception as e:
    print("ERROR:")
    print(e)
