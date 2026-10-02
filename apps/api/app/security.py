"""Password hashing, access tokens and role dependencies."""

from datetime import datetime, timedelta, timezone
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from .database import get_session
from .models import User


PASSWORD_HASHER = PasswordHasher()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def verify_registration_code(request: Request, supplied_code: str) -> bool:
    settings = request.app.state.settings
    if settings.app_env not in {"local", "test"}:
        return False
    return hmac.compare_digest(settings.dev_verification_code, supplied_code)


def create_access_token(user_id: int, secret: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "type": "access", "iat": now, "exp": now + timedelta(minutes=minutes)},
        secret,
        algorithm="HS256",
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    from .main import ApiError

    if credentials is None:
        raise ApiError(401, "UNAUTHORIZED", "请先登录")
    try:
        payload = jwt.decode(credentials.credentials, request.app.state.settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise InvalidTokenError("wrong token type")
        user_id = int(payload["sub"])
    except (InvalidTokenError, ValueError, KeyError):
        raise ApiError(401, "UNAUTHORIZED", "登录已失效") from None
    user = session.get(User, user_id)
    if user is None or user.status != "ACTIVE" or user.deleted_at is not None:
        raise ApiError(401, "UNAUTHORIZED", "登录已失效")
    return user


def require_role(role_code: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        from .main import ApiError

        if role_code not in {role.code for role in user.roles}:
            raise ApiError(403, "FORBIDDEN", "无权访问该角色资源")
        return user

    return dependency

