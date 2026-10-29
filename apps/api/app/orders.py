"""M3 addresses, atomic stock reservation, fulfilment and verified reviews."""
import hashlib
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .commerce import active_offers, commit, fail, file_owned, market_statement, merchant_for, now, record
from .commerce_models import MerchantOffer, MerchantProfile, Product, ProductImage, ProductSku
from .database import get_session
from .models import User
from .order_models import CustomerAddress, Order, OrderEvent, OrderItem, Review, Shipment
from .order_rules import lock_product, write_guard
from .order_schemas import AddressInput, AddressResult, OrderAction, OrderCreate, OrderPage, OrderResult, ReviewInput, ReviewResult
from .security import get_current_user, require_role

router = APIRouter(prefix="/api/v1", tags=["Orders"])


def order_json(session, order):
    result = {k: getattr(order, k) for k in ("id", "order_no", "shop_name", "status", "version", "total_amount", "address_snapshot", "cancellation_reason", "created_at")}
    result["items"] = []
    for item in session.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)):
        entry = {k: getattr(item, k) for k in ("id", "offer_id", "product_id", "product_name", "sku_id", "sku_code", "specification", "cover_file_id", "unit_price", "unit", "quantity")}
        entry["review"] = session.scalar(select(Review).where(Review.order_item_id == item.id))
        if entry["review"]:
            entry["review"] = review_json(entry["review"])
        result["items"].append(entry)
    result["events"] = [{k: getattr(e, k) for k in ("action", "from_status", "to_status", "reason", "created_at")}
        for e in session.scalars(select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id))]
    shipment = session.scalar(select(Shipment).where(Shipment.order_id == order.id))
    result["shipment"] = {k: getattr(shipment, k) for k in ("carrier", "tracking_no", "proof_file_id", "created_at")} if shipment else None
    return result


def review_json(review):
    return {k: getattr(review, k) for k in ("id", "rating", "content", "created_at")}


def visible_order(session, user, order_id, lock=False):
    stmt = select(Order).where(Order.id == order_id)
    order = session.scalar(stmt.with_for_update() if lock else stmt)
    merchant = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
    if order is None or not (order.customer_id == user.id or "ADMIN" in {r.code for r in user.roles}
            or (merchant and merchant.id == order.merchant_id)):
        fail(404, "NOT_FOUND", "订单不存在或无权访问")
    return order


@router.get("/addresses", response_model=list[AddressResult])
def addresses(user: User = Depends(require_role("CUSTOMER")), session: Session = Depends(get_session)):
    return [address_json(a) for a in session.scalars(select(CustomerAddress).where(
        CustomerAddress.user_id == user.id, CustomerAddress.deleted_at.is_(None)).order_by(CustomerAddress.id.desc()))]


def address_json(a):
    return {k: getattr(a, k) for k in ("id", "recipient", "phone", "address")}


@router.post("/addresses", status_code=201, response_model=AddressResult)
def add_address(payload: AddressInput, user: User = Depends(require_role("CUSTOMER")), session: Session = Depends(get_session)):
    address = CustomerAddress(user_id=user.id, **payload.model_dump())
    session.add(address)
    commit(session)
    return address_json(address)


@router.put("/addresses/{address_id}", response_model=AddressResult)
def edit_address(address_id: int, payload: AddressInput, user: User = Depends(require_role("CUSTOMER")), session: Session = Depends(get_session)):
    write_guard(session)
    address = session.scalar(select(CustomerAddress).where(CustomerAddress.id == address_id,
        CustomerAddress.user_id == user.id, CustomerAddress.deleted_at.is_(None)).with_for_update())
    if not address:
        fail(404, "NOT_FOUND", "地址不存在")
    for key, value in payload.model_dump().items():
        setattr(address, key, value)
    commit(session)
    return address_json(address)


@router.delete("/addresses/{address_id}", status_code=204)
def delete_address(address_id: int, user: User = Depends(require_role("CUSTOMER")), session: Session = Depends(get_session)):
    changed = session.execute(update(CustomerAddress).where(CustomerAddress.id == address_id,
        CustomerAddress.user_id == user.id, CustomerAddress.deleted_at.is_(None)).values(deleted_at=now()))
    if changed.rowcount != 1:
        fail(404, "NOT_FOUND", "地址不存在")
    commit(session)


def duplicate_result(session, user_id, key, fingerprint):
    existing = session.scalar(select(Order).where(Order.customer_id == user_id, Order.idempotency_key == key))
    if existing:
        if existing.request_hash != fingerprint:
            fail(409, "IDEMPOTENCY_CONFLICT", "此提交标识已用于另一笔订单，请重新确认")
        return order_json(session, existing)
    return None


@router.post("/orders", status_code=201, response_model=OrderResult)
def create_order(payload: OrderCreate, request: Request, user: User = Depends(require_role("CUSTOMER")), session: Session = Depends(get_session)):
    write_guard(session)
    fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    existing = duplicate_result(session, user.id, payload.idempotency_key, fingerprint)
    if existing:
        return existing
    if len({x.offer_id for x in payload.items}) != len(payload.items):
        fail(422, "DUPLICATE_ITEM", "同一报价请合并数量后提交")
    address = session.scalar(select(CustomerAddress).where(CustomerAddress.id == payload.address_id,
        CustomerAddress.user_id == user.id, CustomerAddress.deleted_at.is_(None)).with_for_update())
    if not address:
        fail(422, "INVALID_ADDRESS", "请选择本人有效收货地址")
    # Lock product rows before offers, matching catalogue mutation lock order.
    ids = [x.offer_id for x in payload.items]
    product_ids = list(session.scalars(select(ProductSku.product_id).join(MerchantOffer, MerchantOffer.sku_id == ProductSku.id)
        .where(MerchantOffer.id.in_(ids)).distinct().order_by(ProductSku.product_id)))
    for product_id in product_ids:
        lock_product(session, product_id)
    selected = []
    for entry in sorted(payload.items, key=lambda x: x.offer_id):
        offer = session.scalar(active_offers().where(MerchantOffer.id == entry.offer_id).with_for_update())
        if not offer:
            fail(409, "OFFER_UNAVAILABLE", "报价已失效或缺货，请重新选择")
        sku = session.scalar(select(ProductSku).where(ProductSku.id == offer.sku_id).with_for_update())
        product = session.scalar(market_statement().where(Product.id == sku.product_id).with_for_update())
        if not product or sku.status != "ACTIVE":
            fail(409, "PRODUCT_UNAVAILABLE", "商品已下架或规格不可用")
        if offer.price != entry.expected_price:
            fail(409, "PRICE_CHANGED", "价格已变化，请刷新商品后重新确认")
        selected.append((entry, offer, sku, product))
    merchants = {o.merchant_id for _, o, _, _ in selected}
    if len(merchants) != 1:
        fail(422, "MULTIPLE_MERCHANTS", "不同商家的商品请分别下单")
    merchant = session.get(MerchantProfile, next(iter(merchants)))
    total = sum(o.price * e.quantity for e, o, _, _ in selected)
    if total > Decimal("9999999999.99"):
        fail(422, "AMOUNT_TOO_LARGE", "订单总额超出范围，请减少数量")
    order = Order(order_no="LM" + uuid.uuid4().hex, customer_id=user.id, merchant_id=merchant.id,
        idempotency_key=payload.idempotency_key, request_hash=fingerprint, total_amount=total,
        shop_name=merchant.shop_name, address_snapshot=address_json(address) | {})
    order.address_snapshot.pop("id")
    session.add(order)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = duplicate_result(session, user.id, payload.idempotency_key, fingerprint)
        if existing:
            return existing
        raise
    for entry, offer, sku, product in selected:
        changed = session.execute(update(MerchantOffer).where(MerchantOffer.id == offer.id,
            MerchantOffer.version == offer.version, MerchantOffer.status == "ACTIVE",
            MerchantOffer.stock_qty >= entry.quantity).values(stock_qty=MerchantOffer.stock_qty-entry.quantity,
                version=MerchantOffer.version+1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            fail(409, "STOCK_CONFLICT", "库存不足或报价已变化，请刷新后重试")
        cover = session.scalar(select(ProductImage.file_id).where(ProductImage.sku_id == sku.id).order_by(ProductImage.sort_order, ProductImage.id).limit(1))
        spec = {k: str(getattr(sku, k)) if getattr(sku, k) is not None else None for k in
            ("color", "size_spec", "material", "power_watt", "color_temperature", "luminous_flux_lm")}
        session.add(OrderItem(order_id=order.id, offer_id=offer.id, sku_id=sku.id, product_id=product.id,
            product_name=product.name, sku_code=sku.sku_code, specification=spec, cover_file_id=cover,
            unit_price=offer.price, unit=offer.unit, quantity=entry.quantity))
    session.add(OrderEvent(order_id=order.id, actor_user_id=user.id, action="CREATE", to_status="PENDING_CONFIRM"))
    record(session, request, user, "order", order.id, "CREATE", after="PENDING_CONFIRM")
    commit(session)
    return order_json(session, order)


def order_page(session, statement, page, page_size):
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    return {"items": [order_json(session, o) for o in session.scalars(statement.order_by(Order.id.desc()).offset((page-1)*page_size).limit(page_size))],
        "total": total, "page": page, "page_size": page_size}


@router.get("/orders", response_model=OrderPage)
def customer_orders(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
        user: User = Depends(require_role("CUSTOMER")), session: Session = Depends(get_session)):
    return order_page(session, select(Order).where(Order.customer_id == user.id), page, page_size)


@router.get("/merchant/orders", response_model=OrderPage)
def merchant_orders(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
        user: User = Depends(require_role("MERCHANT")), session: Session = Depends(get_session)):
    merchant = merchant_for(session, user, approved=False)
    return order_page(session, select(Order).where(Order.merchant_id == merchant.id), page, page_size)


@router.get("/admin/orders", response_model=OrderPage)
def admin_orders(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
        user: User = Depends(require_role("ADMIN")), session: Session = Depends(get_session)):
    return order_page(session, select(Order), page, page_size)


@router.get("/orders/{order_id}", response_model=OrderResult)
def order_detail(order_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return order_json(session, visible_order(session, user, order_id))


@router.post("/orders/{order_id}/actions", response_model=OrderResult)
def order_action(order_id: int, payload: OrderAction, request: Request,
        user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    write_guard(session)
    order = visible_order(session, user, order_id, lock=True)
    merchant = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
    seller_action = payload.action in {"CONFIRM", "REJECT", "SHIP"}
    if (seller_action and (not merchant or merchant.id != order.merchant_id or "MERCHANT" not in {r.code for r in user.roles})) or (not seller_action and order.customer_id != user.id):
        fail(403, "FORBIDDEN", "无权执行此订单操作")
    mapping = {"CONFIRM": (["PENDING_CONFIRM"], "TO_SHIP"), "REJECT": (["PENDING_CONFIRM"], "CANCELLED"),
        "CANCEL": (["PENDING_CONFIRM", "TO_SHIP"], "CANCELLED"), "SHIP": (["TO_SHIP"], "SHIPPED"),
        "RECEIVE": (["SHIPPED"], "COMPLETED")}
    allowed, target = mapping[payload.action]
    if order.status not in allowed or order.version != payload.version:
        fail(409, "ORDER_STATE_CONFLICT", "订单状态已变化，请刷新后重试")
    if target == "CANCELLED" and not payload.reason:
        fail(422, "REASON_REQUIRED", "取消或拒绝时请填写原因")
    if payload.action == "SHIP":
        if not payload.carrier or not payload.tracking_no or not payload.proof_file_id:
            fail(422, "SHIPMENT_REQUIRED", "请填写承运方、运单号并上传发货凭证")
        file_owned(session, payload.proof_file_id, user.id, "SHIPMENT")
        session.add(Shipment(order_id=order.id, carrier=payload.carrier,
            tracking_no=payload.tracking_no, proof_file_id=payload.proof_file_id))
    previous = order.status
    changed = session.execute(update(Order).where(Order.id == order.id, Order.version == payload.version,
        Order.status.in_(allowed)).values(status=target, version=Order.version+1,
        cancellation_reason=payload.reason if target == "CANCELLED" else order.cancellation_reason).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        fail(409, "ORDER_STATE_CONFLICT", "订单状态已变化，请刷新后重试")
    if target == "CANCELLED":
        for item in session.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.offer_id)):
            session.execute(update(MerchantOffer).where(MerchantOffer.id == item.offer_id).values(
                stock_qty=MerchantOffer.stock_qty+item.quantity, version=MerchantOffer.version+1))
    session.add(OrderEvent(order_id=order.id, actor_user_id=user.id, action=payload.action,
        from_status=previous, to_status=target, reason=payload.reason or None))
    record(session, request, user, "order", order.id, payload.action, before=previous, after=target)
    commit(session)
    session.refresh(order)
    return order_json(session, order)


@router.post("/order-items/{item_id}/review", status_code=201, response_model=ReviewResult)
def review_item(item_id: int, payload: ReviewInput, request: Request,
        user: User = Depends(require_role("CUSTOMER")), session: Session = Depends(get_session)):
    write_guard(session)
    item = session.get(OrderItem, item_id)
    if not item:
        fail(404, "NOT_FOUND", "订单项不存在")
    order = session.scalar(select(Order).where(Order.id == item.order_id).with_for_update())
    if order.customer_id != user.id:
        fail(404, "NOT_FOUND", "订单项不存在")
    if order.status != "COMPLETED":
        fail(409, "ORDER_NOT_COMPLETED", "确认收货后才能评价")
    if session.scalar(select(Review.id).where(Review.order_item_id == item_id)):
        fail(409, "REVIEW_EXISTS", "此订单项已经评价")
    review = Review(order_item_id=item_id, customer_id=user.id, product_id=item.product_id, **payload.model_dump())
    session.add(review)
    session.flush()
    record(session, request, user, "review", review.id, "CREATE")
    commit(session)
    return review_json(review)


@router.get("/products/{product_id}/reviews", response_model=list[ReviewResult])
def product_reviews(product_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)):
    if session.scalar(market_statement().where(Product.id == product_id)) is None:
        fail(404, "NOT_FOUND", "商品暂不可查看")
    return [review_json(r) for r in session.scalars(select(Review).where(Review.product_id == product_id)
        .order_by(Review.id.desc()).offset((page-1)*page_size).limit(page_size))]
