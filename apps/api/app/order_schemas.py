from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from .commerce_schemas import Input


class AddressInput(Input):
    recipient: str = Field(min_length=1, max_length=80)
    phone: str = Field(pattern=r"^\+?[0-9]{8,15}$", max_length=20)
    address: str = Field(min_length=5, max_length=255)


class AddressResult(AddressInput):
    id: int


class OrderLine(Input):
    offer_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=999, strict=True)
    expected_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class OrderCreate(Input):
    address_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    items: list[OrderLine] = Field(min_length=1, max_length=20)


class OrderAction(Input):
    version: int = Field(ge=1)
    action: Literal["CONFIRM", "REJECT", "CANCEL", "SHIP", "RECEIVE"]
    reason: str = Field(default="", max_length=500)
    carrier: str = Field(default="", max_length=80)
    tracking_no: str = Field(default="", max_length=100)
    proof_file_id: int | None = Field(default=None, gt=0)


class ReviewInput(Input):
    rating: int = Field(ge=1, le=5, strict=True)
    content: str = Field(min_length=1, max_length=1000)


class ReviewResult(BaseModel):
    id: int
    rating: int
    content: str
    created_at: datetime


class OrderItemResult(BaseModel):
    id: int
    offer_id: int
    product_id: int
    product_name: str
    sku_id: int
    sku_code: str
    specification: dict
    cover_file_id: int | None
    unit_price: Decimal
    unit: str
    quantity: int
    review: ReviewResult | None


class EventResult(BaseModel):
    action: str
    from_status: str | None
    to_status: str
    reason: str | None
    created_at: datetime


class ShipmentResult(BaseModel):
    carrier: str
    tracking_no: str
    proof_file_id: int
    created_at: datetime


class OrderResult(BaseModel):
    id: int
    order_no: str
    shop_name: str
    status: str
    version: int
    total_amount: Decimal
    address_snapshot: AddressInput
    cancellation_reason: str | None
    created_at: datetime
    items: list[OrderItemResult]
    events: list[EventResult]
    shipment: ShipmentResult | None
    simulated: bool = True


class OrderPage(BaseModel):
    items: list[OrderResult]
    total: int
    page: int
    page_size: int
