import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import uuid
from app.database.session import SessionLocal
from app.auth.service import AuthService
from app.repositories.user_repository import UserRepository
from app.auth.schemas import RegisterRequest, LoginRequest
from app.database.models.user import User

db = SessionLocal()
try:
    print("==================================================")
    print("STARTING PHONE & OTP AUTHENTICATION TEST")
    print("==================================================")

    # 1. Generate unique phone number
    test_phone = f"9568987{random.randint(100, 999)}"
    print(f"Using test phone: {test_phone}")

    # 2. Instantiate repository and auth service
    repo = UserRepository(db)
    auth_service = AuthService(repo)

    # 3. Register user
    print("Registering user...")
    register_req = RegisterRequest(
        full_name="Phone User Test",
        phone=test_phone,
        preferred_language="en",
    )
    user = auth_service.register(register_req)
    print(f"-> SUCCESS: Registered user ID={user.id}, email={user.email}, phone={user.phone}")

    # 4. Generate OTP
    from app.auth.service import generate_otp
    print("Generating OTP...")
    otp = generate_otp(test_phone)
    print(f"-> Generated OTP: {otp}")

    # 5. Login
    print("Logging in with OTP...")
    login_req = LoginRequest(
        phone=test_phone,
        otp=otp,
    )
    token_res = auth_service.login(login_req)
    print("-> SUCCESS: Logged in successfully!")
    print(f"Access Token: {token_res['access_token'][:50]}...")
    print(f"Preferred Language: {token_res['preferred_language']}")

    print("==================================================")
    print("ALL PHONE & OTP AUTH TESTS PASSED!")
    print("==================================================")

finally:
    db.close()
