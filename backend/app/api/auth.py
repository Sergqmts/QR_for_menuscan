from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, RegisterResponse, TokenResponse, UserOut
from app.services.auth_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user, token = await register_user(db, data)
    return RegisterResponse(user=UserOut.model_validate(user), access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    token = await login_user(db, data.email, data.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
