"""M1 integration tests against a real migrated SQLite database."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Role, User
from app.security import hash_password


ROOT = Path(__file__).resolve().parents[1]
CODE = "246810"


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_url = f"sqlite:///{(tmp_path / 'm1.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic = Config(str(ROOT / "alembic.ini"))
    command.upgrade(alembic, "head")
    app = create_app(Settings("test", database_url, "test-secret-with-at-least-32-characters", 30, CODE, tmp_path / "uploads"))
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.state.session_factory.kw["bind"].dispose()


def register(client, phone="13800138000"):
    return client.post("/api/v1/auth/register", json={"phone": phone, "verification_code": CODE, "password": "strong-pass-123", "display_name": "测试客户"})


def login(client, account="13800138000", password="strong-pass-123"):
    return client.post("/api/v1/auth/login", json={"account": account, "password": password})


def test_migration_readiness_and_registration(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    response = register(client)
    assert response.status_code == 201
    assert response.json()["roles"] == ["CUSTOMER"]
    assert response.json()["phone_masked"] == "138****8000"
    assert "password" not in response.json()
    duplicate = register(client)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ACCOUNT_EXISTS"
    assert duplicate.json()["request_id"] == duplicate.headers["X-Request-ID"]


def test_login_token_and_current_user(client):
    register(client)
    bad = login(client, password="wrong")
    assert bad.status_code == 401
    assert bad.json()["code"] == "INVALID_CREDENTIALS"
    token = login(client).json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == "测试客户"
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer tampered"}).status_code == 401


def test_role_checks_and_account_revocation(client):
    register(client)
    token = login(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/me", headers=headers).status_code == 403
    assert client.get("/api/v1/merchant/me", headers=headers).status_code == 403

    session_factory = client.app.state.session_factory
    with session_factory.begin() as session:
        admin = User(username="course-admin", password_hash=hash_password("admin-password-123"), display_name="管理员")
        admin.roles.append(session.scalar(select(Role).where(Role.code == "ADMIN")))
        session.add(admin)
    admin_token = login(client, "course-admin", "admin-password-123").json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    assert client.get("/api/v1/admin/me", headers=admin_headers).status_code == 200
    assert "phone_masked" not in client.get("/api/v1/admin/me", headers=admin_headers).json()
    assert client.get("/api/v1/merchant/me", headers=admin_headers).status_code == 403
    with session_factory.begin() as session:
        merchant = User(username="lamp-merchant", password_hash=hash_password("merchant-pass-123"), display_name="商家")
        merchant.roles.append(session.scalar(select(Role).where(Role.code == "MERCHANT")))
        session.add(merchant)
    merchant_token = login(client, "lamp-merchant", "merchant-pass-123").json()["access_token"]
    merchant_headers = {"Authorization": f"Bearer {merchant_token}"}
    assert client.get("/api/v1/merchant/me", headers=merchant_headers).status_code == 200
    assert client.get("/api/v1/admin/me", headers=merchant_headers).status_code == 403
    with session_factory.begin() as session:
        session.scalar(select(User).where(User.username == "course-admin")).status = "DISABLED"
    assert client.get("/api/v1/admin/me", headers=admin_headers).status_code == 401


def test_verification_and_expired_token(client):
    bad_code = client.post("/api/v1/auth/register", json={"phone": "13800138000", "verification_code": "000000", "password": "strong-pass-123", "display_name": "测试客户"})
    assert bad_code.status_code == 422
    assert bad_code.json()["code"] == "INVALID_VERIFICATION_CODE"
    invalid_phone = client.post("/api/v1/auth/register", json={"phone": "abc", "verification_code": CODE, "password": "strong-pass-123", "display_name": "测试客户"})
    assert invalid_phone.status_code == 422
    register(client)
    secret = client.app.state.settings.jwt_secret
    expired = jwt.encode({"sub": "1", "type": "access", "exp": 1}, secret, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
