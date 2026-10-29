"""Create local demonstration accounts and products through the real M2 API.

Run after `alembic upgrade head`. Passwords are generated into ignored .local.
Lamp photos use the documented third-party licenses; prices are demonstration data.
"""

from io import BytesIO
import json
import secrets

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select

from .config import API_ROOT, Settings
from .main import create_app
from .models import Role, User
from .security import hash_password
from .demo_catalog import import_catalog, load_catalog


def illustration(kind="TABLE", color="#c6a76f"):
    image = Image.new("RGB", (640, 640), "#eee9dd")
    draw = ImageDraw.Draw(image)
    draw.ellipse((155, 520, 505, 565), fill="#d4cbbb")
    if kind == "LICENSE":
        draw.rectangle((100, 100, 540, 540), fill="white", outline="#b6ab91", width=4)
        draw.text((160, 290), "DEMO ONLY - NOT A LICENSE", fill="#594f3b")
    elif kind == "PENDANT":
        draw.line((320, 0, 320, 200), fill="#44463b", width=8)
        draw.pieslice((140, 160, 500, 500), 180, 360, fill=color)
        draw.ellipse((140, 315, 500, 365), fill="#fff0b5")
    else:
        draw.rounded_rectangle((275, 250, 365, 530), radius=28, fill="#9c835d")
        draw.ellipse((205, 510, 435, 555), fill="#6e7864")
        draw.polygon([(210, 150), (430, 150), (495, 330), (145, 330)], fill=color)
        draw.ellipse((145, 308, 495, 350), fill="#f6dca0")
    draw.text((25, 600), "LUMIERE / SCHEMATIC DEMO", fill="#8b826d")
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def seed():
    settings = Settings.from_env()
    if settings.app_env != "local":
        raise SystemExit("Demo seeding is restricted to APP_ENV=local")
    catalog = load_catalog()
    app = create_app(settings)
    accounts_path = API_ROOT / ".local" / "demo-accounts.json"
    with app.state.session_factory() as session:
        if session.scalar(select(User).where(User.username == "demo-admin")):
            raise SystemExit("Demo users already exist; no existing accounts or data were changed.")
    accounts = {}
    with app.state.session_factory.begin() as session:
        for name, role, display in [("admin", "ADMIN", "演示管理员"), ("merchant", "MERCHANT", "光和灯饰"),
                                     ("merchant2", "MERCHANT", "暖居灯饰"), ("customer", "CUSTOMER", "演示客户")]:
            password = secrets.token_urlsafe(18)
            username = "demo-" + name
            user = User(username=username, display_name=display, password_hash=hash_password(password))
            user.roles.append(session.scalar(select(Role).where(Role.code == role)))
            session.add(user)
            accounts[name] = {"account": username, "password": password}
    accounts_path.parent.mkdir(parents=True, exist_ok=True)
    accounts_path.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")
    client = TestClient(app)

    def call(method, path, who=None, **kwargs):
        headers = {"Authorization": "Bearer " + tokens[who]} if who else {}
        response = client.request(method, "/api/v1" + path, headers=headers, **kwargs)
        if not response.is_success:
            raise RuntimeError(f"Demo step {method} {path} failed: {response.status_code} {response.text}")
        return response.json()

    tokens = {}
    try:
        for who, credentials in accounts.items():
            tokens[who] = call("POST", "/auth/login", json=credentials)["access_token"]
        for who, shop in [("merchant", "演示·光和灯饰"), ("merchant2", "演示·暖居灯饰")]:
            image = call("POST", "/files", who, data={"purpose": "LICENSE"}, files={"file": ("demo.png", illustration("LICENSE"), "image/png")})
            profile = call("PUT", "/merchant/application", who, json={"shop_name": shop, "legal_name": "演示负责人", "contact_phone": "13800138000", "address": "课程演示地址（虚构）", "business_license_file_id": image["id"]})
            call("POST", f"/admin/merchants/{profile['id']}/audit", "admin", json={"result": "APPROVED", "version": profile["version"], "reason": "仅用于本地课程演示，非真实认证"})
        result = import_catalog(app, call, catalog)
        print(f"Created {result['created']} demo products, 40 offers and 4 local accounts.")
        print(f"Account credentials saved locally only: {accounts_path}")
    finally:
        client.close()
        app.state.session_factory.kw["bind"].dispose()


if __name__ == "__main__":
    seed()
