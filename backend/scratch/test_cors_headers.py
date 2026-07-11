import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://voice-based-customer-care-agent-1.onrender.com/api/v1/chat/"

# 1. Test POST request CORS headers
print("--- TESTING POST CORS ---")
req_post = urllib.request.Request(
    url,
    data=json.dumps({"session_id": "test-session-cors", "message": "hi", "language": "en"}).encode("utf-8"),
    headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Origin": "https://voice-based-customer-care-agent.vercel.app"
    },
    method="POST"
)
try:
    with urllib.request.urlopen(req_post, context=ctx) as response:
        print("Status:", response.status)
        for h, v in response.getheaders():
            if "access-control" in h.lower():
                print(f"{h}: {v}")
except Exception as e:
    print("Post error:", e)

# 2. Test OPTIONS (Preflight) request CORS headers
print("\n--- TESTING OPTIONS PREFLIGHT ---")
req_options = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://voice-based-customer-care-agent.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization"
    },
    method="OPTIONS"
)
try:
    with urllib.request.urlopen(req_options, context=ctx) as response:
        print("Status:", response.status)
        for h, v in response.getheaders():
            if "access-control" in h.lower():
                print(f"{h}: {v}")
except Exception as e:
    print("Options error:", e)
