"""Idempotent local catalog upgrade; preserves accounts, records and audit history."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from .commerce_models import ProductSku
from .config import API_ROOT, DEFAULT_DATABASE_URL, Settings
from .main import create_app

ASSETS = API_ROOT.parents[1] / "assets" / "catalog"
BRAND = "LUMIÈRE 样式演示"
LEGACY = {"DEMO-001-A": "暮光黄铜台灯", "DEMO-002-A": "弧光奶油吊灯", "DEMO-003-A": "森影阅读落地灯"}


def load_catalog():
    catalog = json.loads((ASSETS / "catalog.json").read_text(encoding="utf-8"))
    codes, digests = set(), set()
    for row in catalog["products"]:
        code = row["sku_code"]
        if code in codes or not code.startswith("DEMO-PHOTO-"):
            raise ValueError("Duplicate or non-demo SKU in manifest")
        codes.add(code)
        path = (ASSETS / row["photo"]["file"]).resolve()
        if path.parent != ASSETS.resolve():
            raise ValueError("Photo must be directly inside assets/catalog")
        with Image.open(path) as photo:
            photo.verify()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in digests:
            raise ValueError("Each style must have a distinct photo")
        digests.add(digest)
        if len(row["prices"]) != 2 or min(row["prices"]) <= 0:
            raise ValueError("Two positive demonstration prices required")
    return catalog


def make_call(client, accounts):
    tokens = {}

    def call(method, path, who=None, **kwargs):
        headers = {"Authorization": "Bearer " + tokens[who]} if who else {}
        response = client.request(method, "/api/v1" + path, headers=headers, **kwargs)
        if not response.is_success:
            raise RuntimeError(f"Catalog step {method} {path}: {response.status_code} {response.text}")
        return response.json()

    for who in ("admin", "merchant", "merchant2"):
        if accounts[who]["account"] != "demo-" + who:
            raise ValueError("Only the original local demo accounts may import this catalog")
        tokens[who] = call("POST", "/auth/login", json=accounts[who])["access_token"]
    return call


def import_catalog(app, call, catalog=None):
    if app.state.settings.app_env not in {"local", "test"}:
        raise ValueError("Demo catalog import is disabled outside local/test")
    catalog = catalog or load_catalog()
    categories = {c["code"]: c["id"] for c in call("GET", "/categories")}
    owned = call("GET", "/merchant/products", "merchant")
    existing = {s["sku_code"]: p for p in owned for s in p["skus"]}
    # Preflight every identifier before creating anything. Never take over somebody else's SKU.
    with app.state.session_factory() as session:
        for row in catalog["products"]:
            sku = session.scalar(select(ProductSku).where(ProductSku.sku_code == row["sku_code"]))
            if sku:
                product = existing.get(row["sku_code"])
                if not product or product["brand"] != BRAND or product["name"] != row["name"]:
                    raise ValueError(f"SKU collision or manually changed demo product: {row['sku_code']}")
                if not (sku.extra_attributes or {}).get("demo_catalog"):
                    # A partial API create can be resumed only for an exact matching single SKU.
                    if len(product["skus"]) != 1 or product["status"] != "DRAFT":
                        raise ValueError("Unmarked existing SKU cannot be upgraded automatically")
    created = 0
    # Public catalog defaults to newest first; keep the curated interleaving of lamp types.
    for row in reversed(catalog["products"]):
        product = existing.get(row["sku_code"])
        if product is None:
            photo = row["photo"]
            uploaded = call("POST", "/files", "merchant", data={"purpose": "PRODUCT"},
                files={"file": (photo["file"], (ASSETS / photo["file"]).read_bytes(), "image/jpeg")})
            product = call("POST", "/merchant/products", "merchant", json={
                "category_id": categories[row["category"]], "name": row["name"], "brand": BRAND,
                "style": row["style"], "application_space": row["space"],
                "description": row["description"] + "\n" + catalog["notice"],
                "skus": [{"sku_code": row["sku_code"], "color": row["color"], "image_file_ids": [uploaded["id"]]}]})
            created += 1
        sku_id = product["skus"][0]["id"]
        with app.state.session_factory.begin() as session:
            sku = session.get(ProductSku, sku_id)
            if not (sku.extra_attributes or {}).get("demo_catalog"):
                photo, reference = row["photo"], catalog["price_references"][row["category"]]
                sku.extra_attributes = {"demo_catalog": {
                    "photographer": photo["author"], "platform": photo["platform"], "photo_url": photo["page"],
                    "license_url": photo["license"], "price_reference_url": reference["url"],
                    "price_note": reference["note"], "checked_at": catalog["checked_at"]}}
        if product["status"] == "DRAFT":
            product = call("POST", f"/merchant/products/{product['id']}/submit", "merchant", json={"version": product["version"]})
        if product["status"] == "PENDING":
            product = call("POST", f"/admin/products/{product['id']}/audit", "admin", json={"version": product["version"], "result": "APPROVED", "reason": "课程样式演示：已记录素材许可与定价说明"})
        if product["status"] not in {"APPROVED", "ON_SALE", "OFF_SALE"}:
            raise ValueError("Demo product needs manual review; existing decisions were preserved")
        for index, who in enumerate(("merchant", "merchant2")):
            offers = [o for o in call("GET", "/merchant/offers", who) if o["sku_id"] == sku_id]
            if any(o["status"] == "ACTIVE" for o in offers):
                continue  # Never replace a user-adjusted live price.
            offer = max(offers, key=lambda o: o["id"]) if offers else call("POST", f"/merchant/skus/{sku_id}/offers", who,
                json={"price": row["prices"][index], "stock_qty": 12 + index * 6, "unit": "盏",
                      "remark": "演示报价与模拟库存；按单盏灯具造型计价，不含照片中的家具、安装服务；并非照片原商品的真实售价。"})
            if offer["status"] == "DRAFT":
                offer = call("POST", f"/merchant/offers/{offer['id']}/submit", who, json={"version": offer["version"]})
            if offer["status"] == "PENDING":
                call("POST", f"/admin/offers/{offer['id']}/audit", "admin", json={"version": offer["version"], "result": "APPROVED", "reason": "虚构课程报价；非真实交易承诺"})
            elif offer["status"] != "ACTIVE":
                raise ValueError("Existing offer decision requires manual review; not overwritten")
        # Preserve manual OFF_SALE decisions on subsequent runs.
        if product["status"] == "APPROVED":
            call("POST", f"/merchant/products/{product['id']}/sale", "merchant", json={"version": product["version"], "on_sale": True})
    retired = 0
    for product in owned:
        codes = [s["sku_code"] for s in product["skus"]]
        if len(codes) == 1 and LEGACY.get(codes[0]) == product["name"] and product["brand"] == "LUMIÈRE 演示" and "程序绘制示意图" in (product["description"] or "") and product["status"] == "ON_SALE":
            call("POST", f"/merchant/products/{product['id']}/sale", "merchant", json={"version": product["version"], "on_sale": False})
            retired += 1
    return {"created": created, "legacy_retired": retired, "catalog_size": len(catalog["products"])}


def upgrade():
    settings = Settings.from_env()
    if settings.app_env != "local" or settings.database_url != DEFAULT_DATABASE_URL:
        raise SystemExit("Upgrade is restricted to the default local demonstration SQLite database")
    catalog = load_catalog()  # Check every asset before database writes.
    accounts = json.loads((API_ROOT / ".local" / "demo-accounts.json").read_text(encoding="utf-8"))
    db_path = API_ROOT / ".local" / "lamp_mall.db"
    backup = db_path.with_name("before-photo-catalog-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".db")
    with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            call = make_call(client, accounts)
            print(json.dumps(import_catalog(app, call, catalog), ensure_ascii=False))
        print(f"Recoverable database backup: {backup}")
    finally:
        app.state.session_factory.kw["bind"].dispose()


if __name__ == "__main__":
    upgrade()
