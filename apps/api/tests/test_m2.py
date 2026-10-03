from datetime import timedelta
from io import BytesIO

from PIL import Image
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.commerce import now
from app.commerce_models import MerchantOffer, OperationLog, ProductAudit, Product
from app.models import Role, User
from app.security import create_access_token
from test_m1 import client  # shared real-migration fixture


@pytest.fixture
def actors(client):
    result = {}
    with client.app.state.session_factory.begin() as session:
        for name, role in [("admin", "ADMIN"), ("seller", "MERCHANT"), ("other", "MERCHANT"), ("buyer", "CUSTOMER")]:
            user = User(username=name, display_name=name, password_hash="not-used-by-token-tests")
            user.roles.append(session.scalar(select(Role).where(Role.code == role)))
            session.add(user)
            session.flush()
            result[name] = {"Authorization": "Bearer " + create_access_token(user.id, client.app.state.settings.jwt_secret, 30)}
    return result


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def upload(client, headers, purpose="PRODUCT"):
    data = BytesIO()
    Image.new("RGB", (40, 40), "gold").save(data, "PNG")
    return ok(client.post("/api/v1/files", headers=headers, data={"purpose": purpose}, files={"file": ("lamp.png", data.getvalue(), "image/png")}), 201)


def audit(client, actors, kind, obj, result="APPROVED", reason=""):
    return ok(client.post(f"/api/v1/admin/{kind}/{obj['id']}/audit", headers=actors["admin"],
        json={"version": obj["version"], "result": result, "reason": reason}))


def certified(client, actors, who="seller"):
    license = upload(client, actors[who], "LICENSE")
    payload = {"shop_name": who, "legal_name": "测试负责人", "contact_phone": "13800138000", "address": "演示地址", "business_license_file_id": license["id"]}
    profile = ok(client.put("/api/v1/merchant/application", headers=actors[who], json=payload))
    audit(client, actors, "merchants", profile)
    return profile


def draft(client, actors, who="seller", code="LAMP-001", name="暖光台灯"):
    photo = upload(client, actors[who])
    payload = {"category_id": 3, "name": name, "skus": [{"sku_code": code, "power_watt": "12.00", "color_temperature": "3000K", "image_file_ids": [photo["id"]]}]}
    return ok(client.post("/api/v1/merchant/products", headers=actors[who], json=payload), 201)


def approved_product(client, actors):
    certified(client, actors)
    product = draft(client, actors)
    pending = ok(client.post(f"/api/v1/merchant/products/{product['id']}/submit", headers=actors["seller"], json={"version": product["version"]}), 202)
    audit(client, actors, "products", pending)
    return ok(client.get("/api/v1/merchant/products", headers=actors["seller"]))[0]


def live_offer(client, actors, sku_id, who="seller", price=199, stock=10):
    offer = ok(client.post(f"/api/v1/merchant/skus/{sku_id}/offers", headers=actors[who], json={"price": price, "stock_qty": stock, "unit": "件"}), 201)
    pending = ok(client.post(f"/api/v1/merchant/offers/{offer['id']}/submit", headers=actors[who], json={"version": offer["version"]}), 202)
    audit(client, actors, "offers", pending)
    return pending


def on_sale(client, actors, product):
    return ok(client.post(f"/api/v1/merchant/products/{product['id']}/sale", headers=actors["seller"], json={"version": product["version"], "on_sale": True}))


def test_upload_validation_and_private_license(client, actors):
    image = upload(client, actors["seller"], "LICENSE")
    assert client.get(image["url"]).status_code == 401
    assert client.get(image["url"], headers=actors["other"]).status_code == 403
    assert client.get(image["url"], headers=actors["admin"]).status_code == 200
    assert client.get(image["url"], headers=actors["seller"]).headers["cache-control"] == "no-store"
    bad = client.post("/api/v1/files", headers=actors["seller"], data={"purpose": "PRODUCT"}, files={"file": ("fake.png", b"<script>bad</script>", "image/png")})
    assert bad.status_code == 422
    large = client.post("/api/v1/files", headers=actors["seller"], data={"purpose": "PRODUCT"}, files={"file": ("big.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")})
    assert large.status_code == 413


def test_application_rejection_resubmission_and_audit_permissions(client, actors):
    license = upload(client, actors["buyer"], "LICENSE")
    payload = {"shop_name": "新商家", "legal_name": "负责人", "contact_phone": "13800138000", "address": "测试", "business_license_file_id": license["id"]}
    assert client.put("/api/v1/merchant/application", headers=actors["other"], json=payload).status_code == 422
    profile = ok(client.put("/api/v1/merchant/application", headers=actors["buyer"], json=payload))
    path = f"/api/v1/admin/merchants/{profile['id']}/audit"
    body = {"version": profile["version"], "result": "REJECTED"}
    assert client.post(path, headers=actors["buyer"], json=body).status_code == 403
    assert client.post(path, headers=actors["admin"], json=body).status_code == 422
    audit(client, actors, "merchants", profile, "REJECTED", "图片不清晰")
    rejected = ok(client.get("/api/v1/merchant/application", headers=actors["buyer"]))
    assert rejected["audits"][0]["reason"] == "图片不清晰"
    assert client.put("/api/v1/merchant/application", headers=actors["buyer"], json=payload | {"version": 1}).status_code == 409
    resubmitted = ok(client.put("/api/v1/merchant/application", headers=actors["buyer"], json=payload | {"version": rejected["version"]}))
    audit(client, actors, "merchants", resubmitted)
    assert client.get("/api/v1/merchant/me", headers=actors["buyer"]).status_code == 200


def test_full_workflow_visibility_replacement_and_audit_idempotency(client, actors):
    product = approved_product(client, actors)
    assert client.get("/api/v1/products").json()["total"] == 0
    pending = live_offer(client, actors, product["skus"][0]["id"])
    audit(client, actors, "offers", pending)  # identical retry
    live = on_sale(client, actors, product)
    detail = ok(client.get(f"/api/v1/products/{product['id']}"))
    assert detail["lowest_price"] == 199
    assert client.get(detail["cover_url"]).status_code == 200
    assert "audits" not in detail
    assert "audits" not in detail["skus"][0]["offers"][0]
    live_offer(client, actors, product["skus"][0]["id"], price=159)
    detail = ok(client.get(f"/api/v1/products/{product['id']}"))
    assert len(detail["skus"][0]["offers"]) == 1
    assert detail["lowest_price"] == 159
    assert client.get("/api/v1/products?keyword=不存在").json()["total"] == 0
    assert client.get("/api/v1/products?category_id=1").json()["total"] == 0
    assert client.get("/api/v1/products?sort=price_asc&page_size=1").json()["total"] == 1
    ok(client.post(f"/api/v1/merchant/products/{live['id']}/sale", headers=actors["seller"], json={"version": live["version"], "on_sale": False}))
    assert client.get(f"/api/v1/products/{live['id']}").status_code == 404
    assert client.get(detail["cover_url"]).status_code == 401
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProductAudit)) == 1
        assert session.scalar(select(func.count()).select_from(OperationLog)) >= 10


def test_cross_merchant_access_and_multiple_seller_prices(client, actors):
    product = approved_product(client, actors)
    certified(client, actors, "other")
    assert client.post(f"/api/v1/merchant/products/{product['id']}/submit", headers=actors["other"], json={"version": product["version"]}).status_code == 404
    sku_id = product["skus"][0]["id"]
    offer = live_offer(client, actors, sku_id)
    assert client.post(f"/api/v1/merchant/offers/{offer['id']}/submit", headers=actors["other"], json={"version": offer["version"]}).status_code == 404
    live_offer(client, actors, sku_id, "other", price=129)
    on_sale(client, actors, product)
    detail = ok(client.get(f"/api/v1/products/{product['id']}"))
    assert detail["lowest_price"] == 129
    assert len(detail["skus"][0]["offers"]) == 2
    assert len(ok(client.get("/api/v1/merchant/offers", headers=actors["seller"]))) == 1


def test_stale_versions_and_sku_edits_invalidate_quotes(client, actors):
    product = approved_product(client, actors)
    live_offer(client, actors, product["skus"][0]["id"])
    live = on_sale(client, actors, product)
    assert client.post(f"/api/v1/merchant/products/{live['id']}/sale", headers=actors["seller"], json={"version": 1, "on_sale": False}).status_code == 409
    off = ok(client.post(f"/api/v1/merchant/products/{live['id']}/sale", headers=actors["seller"], json={"version": live["version"], "on_sale": False}))
    sku = off["skus"][0]
    changed = ok(client.put(f"/api/v1/merchant/skus/{sku['id']}", headers=actors["seller"], json={"version": off["version"], "sku_code": sku["sku_code"], "power_watt": 24, "image_file_ids": sku["image_file_ids"]}))
    assert changed["status"] == "DRAFT"
    assert changed["skus"][0]["offers"][0]["status"] == "EXPIRED"
    assert client.post(f"/api/v1/merchant/products/{live['id']}/sale", headers=actors["seller"], json={"version": changed["version"], "on_sale": True}).status_code == 409


def test_invalid_prices_and_database_active_uniqueness(client, actors):
    product = approved_product(client, actors)
    sku = product["skus"][0]["id"]
    for price in [-1, "12.345", "NaN"]:
        assert client.post(f"/api/v1/merchant/skus/{sku}/offers", headers=actors["seller"], json={"price": price, "stock_qty": 1, "unit": "件"}).status_code == 422
    live_offer(client, actors, sku)
    with client.app.state.session_factory() as session:
        current = session.scalar(select(MerchantOffer).where(MerchantOffer.status == "ACTIVE"))
        session.add(MerchantOffer(merchant_id=current.merchant_id, sku_id=sku, price=1, stock_qty=1, status="ACTIVE", active_slot=1))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_stock_and_expiry_filters(client, actors):
    product = approved_product(client, actors)
    live_offer(client, actors, product["skus"][0]["id"], stock=0)
    on_sale(client, actors, product)
    assert client.get("/api/v1/products").json()["total"] == 0
    with client.app.state.session_factory.begin() as session:
        offer = session.scalar(select(MerchantOffer))
        offer.stock_qty = 2
        offer.expired_at = now() - timedelta(seconds=1)
    assert client.get("/api/v1/products").json()["total"] == 0


def test_unapproved_and_wrong_purpose_files_cannot_publish(client, actors):
    photo = upload(client, actors["seller"])
    body = {"category_id": 3, "name": "未认证商品", "skus": [{"sku_code": "NO-CERT", "image_file_ids": [photo["id"]]}]}
    assert client.post("/api/v1/merchant/products", headers=actors["seller"], json=body).status_code == 403
    certified(client, actors)
    private = upload(client, actors["seller"], "LICENSE")
    body["skus"][0]["image_file_ids"] = [private["id"]]
    assert client.post("/api/v1/merchant/products", headers=actors["seller"], json=body).status_code == 422
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 0
    assert client.get(private["url"]).status_code == 401


def test_rejected_product_can_be_edited_and_resubmitted(client, actors):
    certified(client, actors)
    product = draft(client, actors)
    pending = ok(client.post(f"/api/v1/merchant/products/{product['id']}/submit", headers=actors["seller"], json={"version": product["version"]}), 202)
    audit(client, actors, "products", pending, "REJECTED", "请补充商品介绍")
    rejected = ok(client.get("/api/v1/merchant/products", headers=actors["seller"]))[0]
    edited = ok(client.put(f"/api/v1/merchant/products/{product['id']}", headers=actors["seller"], json={"version": rejected["version"], "name": "更正名称", "category_id": 3, "description": "补充介绍"}))
    resubmitted = ok(client.post(f"/api/v1/merchant/products/{product['id']}/submit", headers=actors["seller"], json={"version": edited["version"]}), 202)
    audit(client, actors, "products", resubmitted)
    assert len(ok(client.get("/api/v1/merchant/products", headers=actors["seller"]))[0]["audits"]) == 2


def test_stale_offer_audit_does_not_expire_current_offer(client, actors):
    product = approved_product(client, actors)
    sku = product["skus"][0]["id"]
    live_offer(client, actors, sku)
    next_offer = ok(client.post(f"/api/v1/merchant/skus/{sku}/offers", headers=actors["seller"], json={"price": 99, "stock_qty": 10, "unit": "件"}), 201)
    pending = ok(client.post(f"/api/v1/merchant/offers/{next_offer['id']}/submit", headers=actors["seller"], json={"version": next_offer["version"]}), 202)
    assert client.post(f"/api/v1/admin/offers/{pending['id']}/audit", headers=actors["admin"], json={"version": 1, "result": "APPROVED"}).status_code == 409
    with client.app.state.session_factory() as session:
        assert session.scalar(select(MerchantOffer).where(MerchantOffer.status == "ACTIVE")).price == 199


def test_m2_migration_round_trip_keeps_accounts(client, actors):
    from alembic import command
    from alembic.config import Config
    from test_m1 import ROOT
    config = Config(str(ROOT / "alembic.ini"))
    command.downgrade(config, "20261002_01")
    assert client.get("/health/ready").status_code == 503
    command.upgrade(config, "head")
    assert client.get("/health/ready").status_code == 200
    assert client.get("/api/v1/admin/me", headers=actors["admin"]).status_code == 200
