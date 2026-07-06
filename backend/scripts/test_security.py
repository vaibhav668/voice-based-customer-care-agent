from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)

password = "SupportAI@123"

hashed = hash_password(password)

print(hashed)

print(verify_password(password, hashed))

token = create_access_token(
    {"sub": "admin@gmail.com"}
)

print(token)