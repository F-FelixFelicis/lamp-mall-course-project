"""M3 simulated order fulfilment; no payment or refund records."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .commerce_models import ID, Record
from .database import Base


class CustomerAddress(Record, Base):
    __tablename__ = "customer_addresses"
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id"), index=True)
    recipient: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Order(Record, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("customer_id", "idempotency_key", name="uq_orders_customer_key"),
        CheckConstraint("total_amount >= 0", name="ck_orders_total"),
        CheckConstraint("status IN ('PENDING_CONFIRM','TO_SHIP','SHIPPED','COMPLETED','CANCELLED')", name="ck_orders_status"),
    )
    order_no: Mapped[str] = mapped_column(String(40), unique=True)
    customer_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id"), index=True)
    merchant_id: Mapped[int] = mapped_column(ID, ForeignKey("merchant_profiles.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="PENDING_CONFIRM", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    address_snapshot: Mapped[dict] = mapped_column(JSON)
    shop_name: Mapped[str] = mapped_column(String(120))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))


class OrderItem(Record, Base):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "offer_id", name="uq_order_offer"),
        CheckConstraint("quantity > 0 AND unit_price >= 0", name="ck_order_items_values"))
    order_id: Mapped[int] = mapped_column(ID, ForeignKey("orders.id"), index=True)
    offer_id: Mapped[int] = mapped_column(ID, ForeignKey("merchant_offers.id"))
    sku_id: Mapped[int] = mapped_column(ID, ForeignKey("product_skus.id"), index=True)
    product_id: Mapped[int] = mapped_column(ID, ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(160))
    sku_code: Mapped[str] = mapped_column(String(80))
    specification: Mapped[dict] = mapped_column(JSON)
    cover_file_id: Mapped[int | None] = mapped_column(ID, ForeignKey("uploaded_files.id"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)


class OrderEvent(Record, Base):
    __tablename__ = "order_events"
    order_id: Mapped[int] = mapped_column(ID, ForeignKey("orders.id"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str | None] = mapped_column(String(500))


class Shipment(Record, Base):
    __tablename__ = "shipment_records"
    order_id: Mapped[int] = mapped_column(ID, ForeignKey("orders.id"), unique=True)
    carrier: Mapped[str] = mapped_column(String(80))
    tracking_no: Mapped[str] = mapped_column(String(100))
    proof_file_id: Mapped[int] = mapped_column(ID, ForeignKey("uploaded_files.id"))


class Review(Record, Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),)
    order_item_id: Mapped[int] = mapped_column(ID, ForeignKey("order_items.id"), unique=True)
    customer_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ID, ForeignKey("products.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(String(1000))
