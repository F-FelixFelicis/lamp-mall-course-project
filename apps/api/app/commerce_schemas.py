from decimal import Decimal
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class VersionRequest(Input):
    version: int = Field(ge=1)


class MerchantApplication(Input):
    shop_name: str = Field(min_length=1, max_length=120)
    legal_name: str = Field(min_length=1, max_length=80)
    contact_phone: str = Field(pattern=r"^\+?[0-9]{8,15}$", max_length=20)
    address: str = Field(min_length=1, max_length=255)
    business_license_file_id: int = Field(gt=0)
    version: int | None = Field(default=None, ge=1)


class SkuCreate(Input):
    sku_code: str = Field(min_length=1, max_length=80)
    color: str = Field(default="", max_length=80)
    size_spec: str = Field(default="", max_length=120)
    material: str = Field(default="", max_length=120)
    power_watt: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    color_temperature: str = Field(default="", max_length=60)
    luminous_flux_lm: int | None = Field(default=None, ge=0, le=2147483647)
    image_file_ids: list[int] = Field(min_length=1, max_length=6)


class ProductCreate(Input):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    brand: str = Field(default="", max_length=100)
    style: str = Field(default="", max_length=80)
    application_space: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=5000)
    skus: list[SkuCreate] = Field(min_length=1, max_length=20)


class ProductEdit(Input):
    version: int = Field(ge=1)
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    brand: str = Field(default="", max_length=100)
    style: str = Field(default="", max_length=80)
    application_space: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=5000)


class SkuEdit(SkuCreate):
    version: int = Field(ge=1)


class OfferCreate(Input):
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    stock_qty: int = Field(ge=0, le=2147483647)
    unit: str = Field(min_length=1, max_length=20)
    remark: str = Field(default="", max_length=500)


class AuditRequest(VersionRequest):
    result: Literal["APPROVED", "REJECTED"]
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def rejection_reason(self):
        if self.result == "REJECTED" and not self.reason:
            raise ValueError("驳回时必须填写原因")
        return self


class SaleRequest(VersionRequest):
    on_sale: bool


class AuditResult(BaseModel):
    id: int
    status: str
    version: int


class AuditEntry(BaseModel):
    result: str
    reason: str | None
    version: int
    created_at: datetime


class FileResult(BaseModel):
    id: int
    url: str
    purpose: str
    size_bytes: int


class CategoryResult(BaseModel):
    id: int
    name: str
    code: str


class MerchantResult(BaseModel):
    id: int
    shop_name: str
    legal_name: str
    contact_phone: str
    address: str
    business_license_file_id: int
    certification_status: str
    version: int
    audits: list[AuditEntry]


class OfferResult(BaseModel):
    id: int
    merchant_id: int
    sku_id: int
    sku_code: str
    product_name: str
    shop_name: str
    price: float
    stock_qty: int
    unit: str
    status: str
    version: int
    remark: str | None
    audits: list[AuditEntry] | None = None


class SkuAttributes(BaseModel):
    color: str | None
    size_spec: str | None
    material: str | None
    power_watt: Decimal | None
    color_temperature: str | None
    luminous_flux_lm: int | None


class SkuResult(BaseModel):
    id: int
    sku_code: str
    attributes: SkuAttributes
    image_file_ids: list[int]
    images: list[str]
    offers: list[OfferResult]


class ProductSummary(BaseModel):
    id: int
    name: str
    category_name: str
    status: str
    cover_url: str | None
    lowest_price: float | None


class ProductResult(ProductSummary):
    category_id: int
    brand: str | None
    style: str | None
    application_space: str | None
    description: str | None
    version: int
    skus: list[SkuResult]
    audits: list[AuditEntry] | None = None


class ProductPage(BaseModel):
    items: list[ProductSummary]
    page: int
    page_size: int
    total: int
