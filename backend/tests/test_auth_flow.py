import os
import sys
import uuid
import pytest
from sqlalchemy.orm import Session

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal
from app.database.models.user import User, UserRole
from app.auth.schemas import RegisterRequest, LoginRequest
from app.api.controllers.auth_controller import AuthController
from app.auth.security import decode_access_token, verify_password


def run_auth_tests():
    db = SessionLocal()
    print("Initializing Auth Flow Tests...")

    # Unique email for test
    test_email = f"test_user_{uuid.uuid4().hex[:6]}@example.com"
    test_password = "SecurePassword123!"
    test_name = "Auth Flow Tester"
    test_phone = f"99{uuid.uuid4().hex[:8]}"  # Unique phone to satisfy constraints

    controller = AuthController(db)

    # 1. Test Registration
    print(f"\n1. Attempting to register user: {test_email}...")
    register_data = RegisterRequest(
        full_name=test_name,
        email=test_email,
        phone=test_phone,
        password=test_password
    )
    
    try:
        registered_user = controller.register(register_data)
        print(f"-> Registration successful! Created User ID: {registered_user.id}")
        assert registered_user.email == test_email
        assert registered_user.full_name == test_name
        assert registered_user.role == UserRole.CUSTOMER
        assert verify_password(test_password, registered_user.password_hash)
        print("-> Verification: Password hash successfully verified.")
    except Exception as e:
        print(f"-> Registration FAILED: {e}")
        db.close()
        return False

    # 2. Test Login
    print(f"\n2. Attempting to login with correct credentials...")
    login_data = LoginRequest(
        email=test_email,
        password=test_password
    )
    
    try:
        login_result = controller.login(login_data)
        access_token = login_result.get("access_token")
        token_type = login_result.get("token_type")
        print(f"-> Login successful! Token type: {token_type}")
        print(f"-> Access Token: {access_token[:25]}...")
        assert access_token is not None
        assert token_type == "bearer"
    except Exception as e:
        print(f"-> Login FAILED: {e}")
        db.close()
        return False

    # 3. Test JWT Token Decoding
    print(f"\n3. Attempting to decode and verify JWT payload...")
    try:
        payload = decode_access_token(access_token)
        print(f"-> Decoded Payload: {payload}")
        assert payload is not None
        assert payload.get("sub") == str(registered_user.id)
        assert payload.get("email") == test_email
        assert payload.get("role") == UserRole.CUSTOMER.value
        print("-> Verification: JWT payload contents successfully verified.")
    except Exception as e:
        print(f"-> Token Decoding FAILED: {e}")
        db.close()
        return False

    # 4. Test Login with Incorrect Password
    print(f"\n4. Attempting to login with incorrect password...")
    bad_login_data = LoginRequest(
        email=test_email,
        password="WrongPassword123"
    )
    try:
        controller.login(bad_login_data)
        print("-> Failure: Logged in with incorrect password! (Expected UnauthorizedException)")
        db.close()
        return False
    except Exception as e:
        print(f"-> Success: Login failed as expected: {type(e).__name__}")

    # 5. Verify database record directly
    print(f"\n5. Directly querying database record...")
    db_user = db.query(User).filter_by(email=test_email).first()
    assert db_user is not None
    assert db_user.id == registered_user.id
    print(f"-> DB query successful. User is safely recorded in database.")

    # Clean up test user
    print(f"\n6. Cleaning up test user from database...")
    db.delete(db_user)
    db.commit()
    print("-> Cleanup complete.")

    db.close()
    print("\nALL AUTHENTICATION AND DATABASE INTEGRATION TESTS PASSED WELL! 🎉")
    return True


if __name__ == "__main__":
    success = run_auth_tests()
    if not success:
        sys.exit(1)
