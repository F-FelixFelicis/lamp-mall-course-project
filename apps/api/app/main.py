"""M1 FastAPI application."""

from datetime import datetime, timezone
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .database import get_session, make_engine
from .models import Role, User
from .schemas import ErrorResponse, LoginRequest, RegisterRequest, TokenResponse, UserResponse, public_user
from .security import create_access_token, get_current_user, hash_password, require_role, verify_password, verify_registration_code


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def error_response(request: Request, status_code: int, code: str, message: str, details: dict | None = None):
    payload = ErrorResponse(
        code=code,
        message=message,
        details=details,
        request_id=getattr(request.state, "request_id", "unknown"),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.app_env == "production" and len(settings.jwt_secret) < 32:
        raise ValueError("JWT_SECRET must contain at least 32 characters in production")
    engine = make_engine(settings.database_url)
    app = FastAPI(title="灯具商城 API", version="0.2.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    if settings.app_env in {"local", "test"}:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (5173, 5174, 5175)],
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )
    app.state.settings = settings
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = {"fields": [{"field": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in exc.errors()]}
        return error_response(request, 422, "VALIDATION_ERROR", "请求参数不符合要求", details)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        return error_response(request, 409, "DATA_CONFLICT", "数据发生冲突，请刷新后重试")

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(session: Session = Depends(get_session)):
        try:
            session.execute(text("SELECT 1"))
            role_codes = set(session.scalars(select(Role.code)).all())
            if not {"CUSTOMER", "MERCHANT", "ADMIN"}.issubset(role_codes):
                raise ValueError("role seed missing")
            from .commerce_models import Category
            if session.scalar(select(Category.id).limit(1)) is None:
                raise ValueError("M2 categories missing")
        except (SQLAlchemyError, ValueError):
            raise ApiError(503, "READINESS_FAILED", "数据库迁移或基础角色尚未就绪") from None
        return {"status": "ready"}

    @app.post("/api/v1/auth/register", status_code=201, response_model=UserResponse, response_model_exclude_none=True, responses={409: {"model": ErrorResponse}})
    def register(payload: RegisterRequest, request: Request, session: Session = Depends(get_session)):
        if settings.app_env == "production":
            raise ApiError(503, "SMS_NOT_CONFIGURED", "短信验证码服务尚未配置")
        if not verify_registration_code(request, payload.verification_code):
            raise ApiError(422, "INVALID_VERIFICATION_CODE", "验证码不正确")
        customer_role = session.scalar(select(Role).where(Role.code == "CUSTOMER"))
        if customer_role is None:
            raise ApiError(503, "READINESS_FAILED", "请先运行数据库迁移")
        user = User(
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            roles=[customer_role],
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise ApiError(409, "ACCOUNT_EXISTS", "手机号已注册") from None
        session.refresh(user)
        return public_user(user)

    @app.post("/api/v1/auth/login", response_model=TokenResponse, responses={401: {"model": ErrorResponse}})
    def login(payload: LoginRequest, session: Session = Depends(get_session)):
        user = session.scalar(select(User).where(or_(User.username == payload.account, User.phone == payload.account)))
        if user is None or user.status != "ACTIVE" or user.deleted_at is not None or not verify_password(user.password_hash, payload.password):
            raise ApiError(401, "INVALID_CREDENTIALS", "账号或密码不正确")
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
        return TokenResponse(
            access_token=create_access_token(user.id, settings.jwt_secret, settings.access_token_minutes),
            expires_in=settings.access_token_minutes * 60,
        )

    @app.get("/api/v1/auth/me", response_model=UserResponse, response_model_exclude_none=True, responses={401: {"model": ErrorResponse}})
    def me(user: User = Depends(get_current_user)):
        return public_user(user)

    @app.get("/api/v1/merchant/me", response_model=UserResponse, response_model_exclude_none=True, responses={403: {"model": ErrorResponse}})
    def merchant_me(user: User = Depends(require_role("MERCHANT"))):
        return public_user(user)

    @app.get("/api/v1/admin/me", response_model=UserResponse, response_model_exclude_none=True, responses={403: {"model": ErrorResponse}})
    def admin_me(user: User = Depends(require_role("ADMIN"))):
        return public_user(user)

    from .commerce import router
    app.include_router(router)
    return app


app = create_app()
