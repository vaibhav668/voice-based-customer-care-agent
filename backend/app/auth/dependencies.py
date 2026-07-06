from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.security import decode_access_token
from app.exceptions.common import UnauthorizedException

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    payload = decode_access_token(token)

    if payload is None:
        raise UnauthorizedException("Invalid or expired token")

    return payload


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
):
    if not credentials or not credentials.credentials:
        return None

    try:
        token = credentials.credentials
        return decode_access_token(token)
    except Exception:
        return None