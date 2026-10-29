"""The curated photo catalog is offline, resumable and non-destructive."""
from copy import deepcopy
from sqlalchemy import func, select

from app.commerce_models import MerchantOffer, OperationLog, Product, ProductSku
from app.demo_catalog import import_catalog, load_catalog
from test_m1 import client
from test_m2 import actors, certified, draft, audit, live_offer, on_sale, ok


def caller(client, actors):
    names = {"merchant": "seller", "merchant2": "other", "admin": "admin"}

    def call(method, path, who=None, **kwargs):
        response = client.request(method, "/api/v1" + path, headers=actors[names[who]] if who else {}, **kwargs)
        assert response.is_success, response.text
        return response.json()
    return call


def test_photo_manifest_coverage_and_distinct_assets():
    catalog = load_catalog()
    assert len(catalog["products"]) == 20
    assert {row["category"] for row in catalog["products"]} == {"TABLE", "PENDANT", "FLOOR", "WALL", "CEILING"}
    for row in catalog["products"]:
        assert row["photo"]["author"]
        assert row["photo"]["license"].startswith("https://")
        assert row["category"] in catalog["price_references"]


def test_catalog_import_idempotence_and_public_disclosures(client, actors):
    certified(client, actors)
    certified(client, actors, "other")
    # An unrelated user-created draft must be preserved.
    unrelated = draft(client, actors, code="USER-OWN-LAMP")
    result = import_catalog(client.app, caller(client, actors))
    assert result == {"created": 20, "legacy_retired": 0, "catalog_size": 20}
    page = client.get("/api/v1/products?page_size=12").json()
    assert page["total"] == 20 and len(page["items"]) == 12
    assert all(row["is_demo"] for row in page["items"])
    assert len(client.get("/api/v1/products?page_size=12&page=2").json()["items"]) == 8
    for card in client.get("/api/v1/products?page_size=100").json()["items"]:
        detail = client.get(f"/api/v1/products/{card['id']}").json()
        assert detail["demo_source"]["photographer"]
        assert detail["demo_source"]["checked_at"] == "2026-10-03"
        assert len(detail["skus"][0]["offers"]) == 2
        assert detail["skus"][0]["attributes"].get("power_watt") is None
        assert client.get(card["cover_url"]).status_code == 200
    with client.app.state.session_factory() as session:
        before = session.scalar(select(func.count()).select_from(OperationLog))
        assert session.scalar(select(func.count()).select_from(MerchantOffer)) == 40
    assert import_catalog(client.app, caller(client, actors))["created"] == 0
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(OperationLog)) == before
        assert session.get(Product, unrelated["id"]).status == "DRAFT"


def test_legacy_retirement_preserves_history_and_changed_demo_data(client, actors):
    certified(client, actors)
    certified(client, actors, "other")
    legacy = draft(client, actors, code="DEMO-001-A", name="暮光黄铜台灯")
    pending = ok(client.post(f"/api/v1/merchant/products/{legacy['id']}/submit", headers=actors["seller"], json={"version": legacy["version"]}), 202)
    approved = audit(client, actors, "products", pending)
    live_offer(client, actors, legacy["skus"][0]["id"])
    on_sale(client, actors, approved)
    with client.app.state.session_factory.begin() as session:
        record = session.get(Product, legacy["id"])
        record.brand = "LUMIÈRE 演示"
        record.description = "课程演示灯具，图片为程序绘制示意图；规格和价格均为虚构数据。"
    catalog = deepcopy(load_catalog())
    catalog["products"] = catalog["products"][:1]
    assert import_catalog(client.app, caller(client, actors), catalog)["legacy_retired"] == 1
    with client.app.state.session_factory() as session:
        assert session.get(Product, legacy["id"]).status == "OFF_SALE"
        assert session.get(ProductSku, legacy["skus"][0]["id"]) is not None
    imported = next(p for p in caller(client, actors)("GET", "/merchant/products", "merchant") if p["is_demo"])
    off = ok(client.post(f"/api/v1/merchant/products/{imported['id']}/sale", headers=actors["seller"], json={"version": imported["version"], "on_sale": False}))
    import_catalog(client.app, caller(client, actors), catalog)
    with client.app.state.session_factory() as session:
        assert session.get(Product, off["id"]).status == "OFF_SALE"


def test_catalog_collision_does_not_modify_other_merchants(client, actors):
    import pytest
    certified(client, actors)
    certified(client, actors, "other")
    catalog = load_catalog()
    other = draft(client, actors, who="other", code=catalog["products"][-1]["sku_code"])
    with pytest.raises(ValueError, match="collision"):
        import_catalog(client.app, caller(client, actors), catalog)
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 1
        assert session.get(Product, other["id"]).status == "DRAFT"


def test_fresh_seed_uses_the_same_photo_catalog(client, tmp_path, monkeypatch):
    import json
    from app import seed_demo
    from app.demo_catalog import make_call

    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(seed_demo, "API_ROOT", tmp_path)
    seed_demo.seed()
    accounts = json.loads((tmp_path / ".local" / "demo-accounts.json").read_text(encoding="utf-8"))
    call = make_call(client, accounts)
    assert call("GET", "/products")["total"] == 20
    assert len(call("GET", "/merchant/offers", "merchant")) == 20
    assert len(call("GET", "/merchant/offers", "merchant2")) == 20
    assert call("GET", "/merchant/application", "merchant")["certification_status"] == "APPROVED"
