"""
User auth and profile endpoints.

Supported auth methods:
  - Email / password (register + login)
  - Google OAuth (access_token from expo-auth-session)
  - Apple Sign-In (identity_token from expo-apple-authentication)
  - Guest / anonymous (no credentials, limited session)
  - Forgot-password / reset-password
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.users import (
    ForgotPasswordBody,
    ResetPasswordBody,
    SocialAuthBody,
    TokenResponse,
    UserLogin,
    UserProfile,
    UserProfileUpdate,
    UserRegister,
)

log = logging.getLogger(__name__)
router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

RESET_CODE_TTL = 3600          # 1 hour
RESET_KEY_PREFIX = "nv:reset:"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_access_token(user_id: str) -> tuple[str, int]:
    expire_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(seconds=expire_seconds),
        "iat": now,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire_seconds


def _redis():
    import redis as _r
    return _r.from_url(settings.REDIS_URL, decode_responses=True)


async def _find_or_create_social_user(
    db: AsyncSession,
    *,
    provider: str,
    social_id: str,
    email: str | None,
    full_name: str | None,
) -> User:
    """
    Look up a user by social ID → email → create new.
    Also links social ID to existing email account (account linking).
    """
    id_field = f"{provider}_id"

    # 1. Find by social ID (returning user via same provider)
    stmt = select(User).where(getattr(User, id_field) == social_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user:
        return user

    # 2. Link to existing email account
    if email:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            setattr(existing, id_field, social_id)
            await db.commit()
            await db.refresh(existing)
            return existing

    # 3. Create new user
    new_user = User(
        id=str(uuid.uuid4()),
        email=email or f"{provider}_{social_id}@nutrivision.social",
        hashed_password=_hash_password(secrets.token_hex(32)),  # unusable password
        full_name=full_name,
        auth_provider=provider,
        is_guest=False,
    )
    setattr(new_user, id_field, social_id)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


# ── Email auth ─────────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already registered.")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        hashed_password=_hash_password(body.password),
        full_name=body.full_name,
        auth_provider="email",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token, expires_in = _create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not _verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")

    token, expires_in = _create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in)


# ── Social auth ────────────────────────────────────────────────────────────────

@router.post("/auth/social", response_model=TokenResponse)
async def social_auth(body: SocialAuthBody, db: AsyncSession = Depends(get_db)):
    """
    Exchange a provider token for a NutriVision JWT.
    Handles Google (access_token) and Apple (identity_token).
    Creates the user on first sign-in; links on subsequent ones.
    """
    if body.provider == "google":
        if not body.access_token:
            raise HTTPException(400, "access_token required for Google auth.")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {body.access_token}"},
                )
            if resp.status_code != 200:
                raise HTTPException(401, "Invalid Google token.")
            data = resp.json()
        except httpx.RequestError as exc:
            log.error("Google userinfo request failed: %s", exc)
            raise HTTPException(503, "Could not verify Google token — try again.")

        user = await _find_or_create_social_user(
            db,
            provider="google",
            social_id=data["id"],
            email=data.get("email"),
            full_name=data.get("name"),
        )

    elif body.provider == "apple":
        if not body.identity_token:
            raise HTTPException(400, "identity_token required for Apple auth.")
        try:
            # Fetch Apple's public JWKS
            async with httpx.AsyncClient(timeout=10) as client:
                keys_resp = await client.get("https://appleid.apple.com/auth/keys")
            keys = keys_resp.json().get("keys", [])

            # Decode header to find key ID
            header = jwt.get_unverified_header(body.identity_token)
            kid = header.get("kid")
            key = next((k for k in keys if k.get("kid") == kid), None)
            if not key:
                raise HTTPException(401, "Apple public key not found.")

            payload = jwt.decode(
                body.identity_token,
                key,
                algorithms=["RS256"],
                audience=settings.APPLE_BUNDLE_ID,
                options={"verify_exp": True},
            )
        except JWTError as exc:
            log.warning("Apple token verification failed: %s", exc)
            raise HTTPException(401, "Invalid Apple identity token.")
        except httpx.RequestError as exc:
            log.error("Apple JWKS request failed: %s", exc)
            raise HTTPException(503, "Could not verify Apple token — try again.")

        user = await _find_or_create_social_user(
            db,
            provider="apple",
            social_id=payload["sub"],
            email=payload.get("email"),
            full_name=body.full_name,
        )

    else:
        raise HTTPException(400, f"Unsupported provider: {body.provider}")

    token, expires_in = _create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in)


# ── Guest auth ─────────────────────────────────────────────────────────────────

@router.post("/auth/guest", response_model=TokenResponse, status_code=201)
async def guest_login(db: AsyncSession = Depends(get_db)):
    """
    Create a temporary anonymous account.
    Guest accounts have is_guest=True and limited data retention.
    The frontend can prompt upgrade to a full account later.
    """
    guest_id = str(uuid.uuid4())
    user = User(
        id=guest_id,
        email=f"guest_{guest_id}@nutrivision.guest",
        hashed_password=_hash_password(secrets.token_hex(32)),
        full_name="Guest",
        auth_provider="guest",
        is_guest=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token, expires_in = _create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in)


# ── Password reset ─────────────────────────────────────────────────────────────

@router.post("/auth/forgot-password", status_code=202)
async def forgot_password(body: ForgotPasswordBody, db: AsyncSession = Depends(get_db)):
    """
    Initiate password reset. Always returns 202 to avoid email enumeration.
    In production: send email with reset link.
    In development: the reset code is logged to the API console.
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user and not user.is_guest:
        code = secrets.token_urlsafe(8)
        try:
            r = _redis()
            r.setex(f"{RESET_KEY_PREFIX}{code}", RESET_CODE_TTL, user.id)
        except Exception:
            pass  # Redis unavailable — still return 202 gracefully

        # TODO(production): Send email via SES / SendGrid with reset link
        log.info("PASSWORD RESET code for %s: %s", body.email, code)

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/auth/reset-password", status_code=200)
async def reset_password(body: ResetPasswordBody, db: AsyncSession = Depends(get_db)):
    """
    Complete password reset. Consumes the one-time code from Redis.
    """
    try:
        r = _redis()
        user_id = r.get(f"{RESET_KEY_PREFIX}{body.code}")
    except Exception:
        user_id = None

    if not user_id:
        raise HTTPException(400, "Reset code is invalid or has expired.")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")

    user.hashed_password = _hash_password(body.new_password)
    await db.commit()

    # Invalidate the code
    try:
        _redis().delete(f"{RESET_KEY_PREFIX}{body.code}")
    except Exception:
        pass

    return {"message": "Password updated successfully."}


# ── Profile ────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserProfile)
async def update_profile(
    body: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user
