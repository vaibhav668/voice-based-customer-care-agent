import sys
sys.path.append('.')
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest
from app.database.session import SessionLocal
from app.database.models.user import User

db = SessionLocal()
user = db.query(User).filter_by(email="vaibhav@gmail.com").first()
user_id = str(user.id) if user else None
print(f"Logged in as user_id: {user_id}")

chat_service = ChatService(db)

# 1. Test Luggage Policy
req1 = ChatRequest(message="tell me the luggage policy", session_id="test_session")
res1 = chat_service.process(req1, user_id=user_id)
print("\nResponse to 'tell me the luggage policy':")
try:
    print(res1.get("response").encode('ascii', 'replace').decode('ascii'))
except Exception:
    pass

# 2. Test Booking status BK-1234
req2 = ChatRequest(message="show me the booking status of BK-1234", session_id="test_session")
res2 = chat_service.process(req2, user_id=user_id)
print("\nResponse to 'show me the booking status of BK-1234':")
try:
    print(res2.get("response").encode('ascii', 'replace').decode('ascii'))
except Exception:
    pass

db.close()
