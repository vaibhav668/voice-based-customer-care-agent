import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from app.database.session import SessionLocal, engine
from app.database.models.user import User, UserRole
from app.auth.security import hash_password
from sqlalchemy import text, inspect
from app.database.base import Base

# 0. Simulate startup database migration to add column if not exists
with engine.begin() as conn:
    inspector = inspect(conn)
    if "users" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("users")]
        if "name_encrypted" not in columns:
            print("Applying startup database migration: Adding name_encrypted column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN name_encrypted VARCHAR(255)"))
            if "full_name" in columns:
                from app.database.models.user import encrypt_field
                res = conn.execute(text("SELECT id, full_name FROM users")).fetchall()
                for row in res:
                    encrypted = encrypt_field(row[1])
                    conn.execute(
                        text("UPDATE users SET name_encrypted = :enc WHERE id = :id"),
                        {"enc": encrypted, "id": row[0]}
                    )

# Create all database tables
Base.metadata.create_all(bind=engine)

# Ensure full_name column exists (for compatibility if table was newly created)
with engine.begin() as conn:
    inspector = inspect(conn)
    if "users" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("users")]
        if "full_name" not in columns:
            print("Applying startup database migration: Adding full_name column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(100)"))

db = SessionLocal()
try:
    print("==================================================")
    print("STARTING SECURITY & FIELD-LEVEL ENCRYPTION TEST")
    print("==================================================")

    # Generate test inputs
    test_email = f"test_enc_{random.randint(100, 999)}@example.com"
    test_phone = f"9876543{random.randint(100, 999)}"
    test_name = "Secret Passenger PII Name"

    # 1. Register/Save User
    print("Saving user with sensitive name...")
    new_user = User(
        full_name=test_name,
        email=test_email,
        phone=test_phone,
        password_hash=hash_password("password123"),
        role=UserRole.CUSTOMER,
        is_active=True,
        is_verified=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    user_id = new_user.id
    print(f"-> Saved user successfully (ID: {user_id})")

    # 2. Directly execute SQL to verify raw DB dump value is encrypted
    print("\nExecuting direct raw SQL to check DB storage content...")
    raw_row = db.execute(
        text("SELECT name_encrypted FROM users WHERE id = :uid"),
        {"uid": user_id.hex}
    ).fetchone()

    db_value = raw_row[0]
    print(f"-> Raw value stored in database: '{db_value}'")
    assert db_value != test_name, "ERROR: Raw name is stored in plaintext!"
    print("-> SUCCESS: Plaintext name is not visible in raw DB table dump!")

    # 3. Retrieve through SQLAlchemy ORM to verify transparent decryption
    print("\nRetrieving user through ORM...")
    orm_user = db.get(User, user_id)
    print(f"-> ORM Decrypted value: '{orm_user.full_name}'")
    assert orm_user.full_name == test_name, "ERROR: Decryption output does not match original plaintext!"
    print("-> SUCCESS: Transparent decryption functions correctly via hybrid properties!")

    # 4. Verify Recording URL access gating logic
    print("\nTesting recording_url gating logic...")
    from app.database.models.conversation import Conversation
    from app.api.routes.conversation import get_conversation_detail
    import uuid

    # Create dummy conversation with recording_url
    dummy_conv = Conversation(
        session_id=f"test-gating-{random.randint(1000,9999)}",
        status="CLOSED",
        language="en",
        channel="VOICE",
        recording_url="https://s3.amazonaws.com/encrypted-bucket/call-rec-123.webm"
    )
    db.add(dummy_conv)
    db.commit()
    db.refresh(dummy_conv)

    # Call route as non-admin customer
    import json
    non_admin_ctx = {"sub": str(uuid.uuid4()), "role": "CUSTOMER"}
    res_non_admin = get_conversation_detail(str(dummy_conv.id), current_user=non_admin_ctx, db=db)
    content_non_admin = json.loads(res_non_admin.body.decode('utf-8'))
    non_admin_url = content_non_admin["data"]["recording_url"]
    print(f"-> CUSTOMER role response recording_url: {non_admin_url}")
    assert non_admin_url is None, "ERROR: Recording URL was leaked to non-admin!"
    print("-> SUCCESS: Recording URL redacted for CUSTOMER!")

    # Call route as admin
    admin_ctx = {"sub": str(uuid.uuid4()), "role": "ADMIN"}
    res_admin = get_conversation_detail(str(dummy_conv.id), current_user=admin_ctx, db=db)
    content_admin = json.loads(res_admin.body.decode('utf-8'))
    admin_url = content_admin["data"]["recording_url"]
    print(f"-> ADMIN role response recording_url: {admin_url}")
    assert admin_url == dummy_conv.recording_url, "ERROR: Recording URL was hidden from admin!"
    print("-> SUCCESS: Recording URL exposed to ADMIN!")

    print("==================================================")
    print("ALL FIELD-LEVEL ENCRYPTION & ACCESS GATING TESTS PASSED!")
    print("==================================================")

finally:
    db.close()
