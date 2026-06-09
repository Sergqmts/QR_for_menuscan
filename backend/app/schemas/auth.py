from pydantic import BaseModel, EmailStr
import uuid


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400


class RegisterResponse(BaseModel):
    user: UserOut
    access_token: str
    token_type: str = "bearer"
