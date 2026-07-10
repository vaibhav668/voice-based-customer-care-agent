from pydantic import BaseModel


class SendOTPRequest(BaseModel):
    phone: str


class RegisterRequest(BaseModel):
    full_name: str
    phone: str
    preferred_language: str = "en"


class LoginRequest(BaseModel):
    phone: str
    otp: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    preferred_language: str = "en"