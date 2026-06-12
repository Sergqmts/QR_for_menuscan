import secrets
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
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


_HANDOFF_PREFIX = "kitchen_handoff:"
_HANDOFF_TTL = 60  # seconds — code expires after 60 s and is deleted on first use


@router.post("/kitchen-handoff")
async def kitchen_handoff(
    request: Request,
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
):
    """Issue a 60-second single-use handoff code for the Kitchen Display.

    The opaque code is stored in Redis mapping to the caller's JWT.
    The kitchen WS endpoint exchanges it once and then deletes the key,
    so the long-lived JWT never appears in any URL or HTML.
    """
    raw_token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    code = secrets.token_urlsafe(32)
    await redis.set(f"{_HANDOFF_PREFIX}{code}", raw_token, ex=_HANDOFF_TTL)
    return {"code": code}
