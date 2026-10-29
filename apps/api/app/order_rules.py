"""Locks shared by stock reservations and catalogue mutations."""
from sqlalchemy import select
from .commerce_models import Product
from .order_models import Order, OrderItem


def write_guard(session):
    # SQLite SELECTs do not begin a DBAPI transaction. Reserve its writer before
    # reading mutable business state; MySQL uses row locks instead.
    if session.bind.dialect.name == "sqlite":
        connection = session.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")


def lock_product(session, product_id):
    return session.scalar(select(Product).where(Product.id == product_id).with_for_update())


def has_unshipped(session, sku_id, merchant_id=None):
    stmt = select(OrderItem.id).join(Order).where(OrderItem.sku_id == sku_id,
        Order.status.in_(["PENDING_CONFIRM", "TO_SHIP"]))
    if merchant_id is not None:
        stmt = stmt.where(Order.merchant_id == merchant_id)
    return session.scalar(stmt.limit(1).with_for_update()) is not None
