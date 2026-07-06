from pydantic import BaseModel, EmailStr


class UpdateLanguageRequest(BaseModel):
    preferred_language: str


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str
    role: str
    preferred_language: str = "en"
