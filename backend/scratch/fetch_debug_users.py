import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://voice-based-customer-care-agent-1.onrender.com/api/v1/health/?nocache=1982736"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req, context=ctx) as response:
        html = response.read().decode("utf-8")
        print("RESPONSE:")
        print(html)
except Exception as e:
    print("ERROR FETCHING:")
    print(e)
