"""Runtime settings for the M1 backend."""

from dataclasses import dataclass
import os
from pathlib import Path
import secrets


API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{(API_ROOT / '.local' / 'lamp_mall.db').as_posix()}"


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    jwt_secret: str
    access_token_minutes: int = 30
    dev_verification_code: str = "123456"
    upload_dir: Path = API_ROOT / ".local" / "uploads"

    @classmethod
    def from_env(cls) -> "Settings":
        app_env = os.getenv("APP_ENV", "local").lower()
        if app_env not in {"local", "test", "production"}:
            raise ValueError("APP_ENV must be local, test, or production")
        jwt_secret = os.getenv("JWT_SECRET")
        if app_env == "production" and (not jwt_secret or len(jwt_secret) < 32):
            raise ValueError("JWT_SECRET must contain at least 32 characters in production")
        return cls(
            app_env=app_env,
            database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
            jwt_secret=jwt_secret or secrets.token_urlsafe(48),
            access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "30")),
            dev_verification_code=os.getenv("DEV_VERIFICATION_CODE", "123456"),
            upload_dir=Path(os.getenv("UPLOAD_DIR", str(API_ROOT / ".local" / "uploads"))),
        )
