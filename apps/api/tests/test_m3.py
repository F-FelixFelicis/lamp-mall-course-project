from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import func, select

from app.commerce_models import MerchantOffer, Product
from app.order_models import Order, OrderEvent, OrderItem
from test_m1 import client
from test_m2 import actors, approved_product, certified, live_offer, ok, on_sale, upload


@pytest.fixture
def market(client, actors):
    p = approved_product(client, actors)
    o = live_offer(client, actors, p["skus"][0]["id"], stock=3)
    on_sale(client, actors, p)
    a = ok(client.post("/api/v1/addresses", headers=actors["buyer"], json={"recipient": "测试顾客", "phone": "13800138000", "address": "课程演示地址一号"}), 201)
    return p, o, a


def body(market, quantity=1, key=None):
    _, o, a = market
    return {"address_id": a["id"], "idempotency_key": key or uuid.uuid4().hex,
        "items": [{"offer_id": o["id"], "quantity": quantity, "expected_price": "199.00"}]}


def place(client, actors, market, quantity=1):
    return ok(client.post("/api/v1/orders", headers=actors["buyer"], json=body(market, quantity)), 201)


def act(client, actors, order, action, who, **extra):
    return client.post(f"/api/v1/orders/{order['id']}/actions", headers=actors[who],
        json={"version": order["version"], "action": action, **extra})


def stock(client, market):
    with client.app.state.session_factory() as s:
        return s.get(MerchantOffer, market[1]["id"]).stock_qty


def test_fulfilment_review_and_private_shipment(client, actors, market):
    order = place(client, actors, market, 2)
    assert order["status"] == "PENDING_CONFIRM" and order["simulated"] is True
    assert Decimal(order["total_amount"]) == 398 and stock(client, market) == 1
    item = order["items"][0]
    assert client.post(f"/api/v1/order-items/{item['id']}/review", headers=actors["buyer"], json={"rating":5,"content":"好灯"}).status_code == 409
    confirmed = ok(act(client, actors, order, "CONFIRM", "seller"))
    assert confirmed["status"] == "TO_SHIP"
    assert act(client, actors, confirmed, "SHIP", "seller").status_code == 422
    proof = upload(client, actors["seller"], "SHIPMENT")
    assert client.get(proof["url"], headers=actors["buyer"]).status_code == 403
    shipped = ok(act(client, actors, confirmed, "SHIP", "seller", carrier="模拟承运方", tracking_no="DEMO-001", proof_file_id=proof["id"]))
    assert shipped["status"] == "SHIPPED"
    assert client.get(proof["url"]).status_code == 401
    assert client.get(proof["url"], headers=actors["buyer"]).status_code == 200
    assert client.get(proof["url"], headers=actors["other"]).status_code == 403
    assert act(client, actors, shipped, "CANCEL", "buyer", reason="取消").status_code == 409
    completed = ok(act(client, actors, shipped, "RECEIVE", "buyer"))
    assert completed["status"] == "COMPLETED" and len(completed["events"]) == 4
    review = {"rating":5,"content":"课程测试评价"}
    ok(client.post(f"/api/v1/order-items/{item['id']}/review", headers=actors["buyer"], json=review),201)
    assert client.post(f"/api/v1/order-items/{item['id']}/review", headers=actors["buyer"], json=review).status_code == 409
    public = ok(client.get(f"/api/v1/products/{market[0]['id']}/reviews"))
    assert len(public) == 1 and "customer_id" not in public[0]
    assert stock(client, market) == 1


@pytest.mark.parametrize("action,state", [("REJECT",False),("CANCEL",False),("CANCEL",True)])
def test_cancel_reject_release_once(client, actors, market, action, state):
    order = place(client, actors, market)
    if state:
        order = ok(act(client, actors, order, "CONFIRM", "seller"))
    who = "seller" if action == "REJECT" else "buyer"
    assert act(client, actors, order, action, who).status_code == 422
    cancelled = ok(act(client, actors, order, action, who, reason="课程演示取消"))
    assert cancelled["status"] == "CANCELLED" and stock(client, market) == 3
    assert act(client, actors, cancelled, action, who, reason="重复").status_code == 409
    assert stock(client, market) == 3


def test_idempotency_stock_and_payload_conflict(client, actors, market):
    payload = body(market)
    first = ok(client.post("/api/v1/orders", headers=actors["buyer"], json=payload),201)
    retry = ok(client.post("/api/v1/orders", headers=actors["buyer"], json=payload),201)
    assert first["id"] == retry["id"] and stock(client, market) == 2
    payload["items"][0]["quantity"] = 2
    assert client.post("/api/v1/orders", headers=actors["buyer"], json=payload).status_code == 409
    assert stock(client, market) == 2


def test_atomic_multi_line_failure_and_invalid_input(client, actors, market):
    for field, value in [("quantity", 0), ("quantity", 1.2), ("expected_price", "198.99")]:
        payload = body(market)
        payload["items"][0][field] = value
        assert client.post("/api/v1/orders", headers=actors["buyer"], json=payload).status_code in {409,422}
    assert client.post("/api/v1/orders", headers=actors["buyer"], json=body(market,4)).status_code == 409
    duplicate = body(market)
    duplicate["items"].append(duplicate["items"][0].copy())
    assert client.post("/api/v1/orders", headers=actors["buyer"], json=duplicate).status_code == 422
    assert stock(client, market) == 3
    with client.app.state.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Order)) == 0


def test_address_ownership_order_roles_and_snapshots(client, actors, market):
    payload = body(market)
    assert client.post("/api/v1/orders", json=payload).status_code == 401
    assert client.post("/api/v1/orders", headers=actors["other"], json=payload).status_code == 403
    from app.models import Role, User
    from app.security import create_access_token
    with client.app.state.session_factory.begin() as s:
        u=User(username="buyer2",display_name="另一顾客",password_hash="unused",roles=[s.scalar(select(Role).where(Role.code=="CUSTOMER"))])
        s.add(u); s.flush()
        other={"Authorization":"Bearer "+create_access_token(u.id,client.app.state.settings.jwt_secret,30)}
    assert client.post("/api/v1/orders",headers=other,json=payload).status_code==422
    address_path=f"/api/v1/addresses/{market[2]['id']}"
    updated={"recipient":"改后姓名","phone":"13900139000","address":"修改后的演示地址"}
    assert client.put(address_path,headers=other,json=updated).status_code==404
    order=place(client,actors,market)
    assert client.get(f"/api/v1/orders/{order['id']}",headers=other).status_code==404
    assert act(client,actors,order,"CONFIRM","admin").status_code==403
    assert act(client,actors,order,"RECEIVE","seller").status_code==403
    assert client.get("/api/v1/admin/orders",headers=actors["buyer"]).status_code==403
    assert ok(client.get("/api/v1/admin/orders",headers=actors["admin"]))["total"]==1
    certified(client,actors,"other")
    assert ok(client.get("/api/v1/merchant/orders",headers=actors["other"]))["total"]==0
    assert client.get(f"/api/v1/orders/{order['id']}",headers=actors["other"]).status_code==404
    ok(client.put(address_path,headers=actors["buyer"],json=updated))
    assert client.delete(address_path,headers=other).status_code==404
    assert client.delete(address_path,headers=actors["buyer"]).status_code==204
    with client.app.state.session_factory.begin() as s:
        s.get(Product, market[0]["id"]).name="改后商品名"
        s.get(MerchantOffer, market[1]["id"]).price=Decimal("888.00")
    snapshot=ok(client.get(f"/api/v1/orders/{order['id']}",headers=actors["buyer"]))
    assert snapshot["address_snapshot"]["recipient"]=="测试顾客"
    assert snapshot["items"][0]["product_name"]=="暖光台灯"
    assert Decimal(snapshot["items"][0]["unit_price"])==199


@pytest.mark.parametrize("same_key",[False,True])
def test_concurrent_last_stock_and_duplicate_submit(client, actors, market, same_key):
    with client.app.state.session_factory.begin() as s:
        s.get(MerchantOffer,market[1]["id"]).stock_qty=1
    key=uuid.uuid4().hex
    bodies=[body(market,key=key if same_key else None) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda b:client.post("/api/v1/orders",headers=actors["buyer"],json=b),bodies))
    assert sorted(r.status_code for r in responses)==([201,201] if same_key else [201,409])
    assert stock(client,market)==0
    with client.app.state.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Order))==1
        assert s.scalar(select(func.count()).select_from(OrderEvent))==1


def test_quote_replacement_guard_and_release(client, actors, market):
    order=place(client,actors,market)
    offer=ok(client.post(f"/api/v1/merchant/skus/{market[0]['skus'][0]['id']}/offers",headers=actors["seller"],json={"price":180,"stock_qty":2,"unit":"件"}),201)
    pending=ok(client.post(f"/api/v1/merchant/offers/{offer['id']}/submit",headers=actors["seller"],json={"version":offer["version"]}),202)
    audit_path=f"/api/v1/admin/offers/{offer['id']}/audit"
    audit={"version":pending["version"],"result":"APPROVED"}
    assert client.post(audit_path,headers=actors["admin"],json=audit).json()["code"]=="UNSHIPPED_ORDERS"
    ok(act(client,actors,order,"CANCEL","buyer",reason="取消"))
    assert stock(client,market)==3
    ok(client.post(audit_path,headers=actors["admin"],json=audit))


def test_unavailable_and_multi_merchant_orders(client,actors,market):
    certified(client,actors,"other")
    second=live_offer(client,actors,market[0]["skus"][0]["id"],who="other")
    payload=body(market)
    payload["items"].append({"offer_id":second["id"],"quantity":1,"expected_price":"199"})
    assert client.post("/api/v1/orders",headers=actors["buyer"],json=payload).status_code==422
    with client.app.state.session_factory.begin() as s:
        s.get(Product,market[0]["id"]).status="OFF_SALE"
    assert client.post("/api/v1/orders",headers=actors["buyer"],json=body(market)).status_code==409
    assert stock(client,market)==3


def test_multi_item_failure_rolls_back_all_reservations(client,actors,market):
    from test_m2 import draft, audit
    second = draft(client, actors, code="SECOND-LAMP")
    pending=ok(client.post(f"/api/v1/merchant/products/{second['id']}/submit",headers=actors["seller"],json={"version":second["version"]}),202)
    approved=audit(client,actors,"products",pending)
    offer=live_offer(client,actors,second["skus"][0]["id"],stock=1)
    on_sale(client,actors,approved)
    payload=body(market)
    payload["items"].append({"offer_id":offer["id"],"quantity":2,"expected_price":"199.00"})
    assert client.post("/api/v1/orders",headers=actors["buyer"],json=payload).status_code==409
    assert stock(client,market)==3
    with client.app.state.session_factory() as s:
        assert s.get(MerchantOffer,offer["id"]).stock_qty==1
        assert s.scalar(select(func.count()).select_from(Order))==0
        assert s.scalar(select(func.count()).select_from(OrderItem))==0
    payload["items"][1]["quantity"]=1
    order=ok(client.post("/api/v1/orders",headers=actors["buyer"],json=payload),201)
    assert len(order["items"])==2 and Decimal(order["total_amount"])==398


def test_concurrent_cancel_releases_only_once(client,actors,market):
    order=place(client,actors,market)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:act(client,actors,order,"CANCEL","buyer",reason="取消"),range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    assert stock(client,market)==3
    with client.app.state.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(OrderEvent).where(OrderEvent.action=="CANCEL"))==1


def test_snapshot_image_access_after_unlisting(client,actors,market):
    order=place(client,actors,market)
    photo=order["items"][0]["cover_file_id"]
    with client.app.state.session_factory.begin() as s:
        s.get(Product,market[0]["id"]).status="OFF_SALE"
    path=f"/api/v1/files/{photo}/content"
    assert client.get(path).status_code==401
    assert client.get(path,headers=actors["buyer"]).status_code==200
    assert client.get(path,headers=actors["other"]).status_code==403


def test_shipping_requires_own_proof_and_sku_guard(client,actors,market):
    order=place(client,actors,market)
    order=ok(act(client,actors,order,"CONFIRM","seller"))
    wrong=upload(client,actors["seller"],"PRODUCT")
    assert act(client,actors,order,"SHIP","seller",carrier="测试",tracking_no="TEST",proof_file_id=wrong["id"]).status_code==422
    others=upload(client,actors["other"],"SHIPMENT")
    assert act(client,actors,order,"SHIP","seller",carrier="测试",tracking_no="TEST",proof_file_id=others["id"]).status_code==422
    p=ok(client.get("/api/v1/merchant/products",headers=actors["seller"]))[0]
    off=ok(client.post(f"/api/v1/merchant/products/{p['id']}/sale",headers=actors["seller"],json={"version":p["version"],"on_sale":False}))
    sku=p["skus"][0]
    changed=client.put(f"/api/v1/merchant/skus/{sku['id']}",headers=actors["seller"],json={"version":off["version"],"sku_code":sku["sku_code"],"image_file_ids":sku["image_file_ids"]})
    assert changed.status_code==409 and changed.json()["code"]=="UNSHIPPED_ORDERS"
