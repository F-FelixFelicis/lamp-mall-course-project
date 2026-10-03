"""M2 merchant, catalog, pricing and audit persistence."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

ID = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite")


class Record:
    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class UploadedFile(Record, Base):
    __tablename__ = "uploaded_files"
    owner_user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    access_level: Mapped[str] = mapped_column(String(20), default="PRIVATE")
    purpose: Mapped[str] = mapped_column(String(20))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class MerchantProfile(Record, Base):
    __tablename__ = "merchant_profiles"
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id"), unique=True)
    shop_name: Mapped[str] = mapped_column(String(120))
    legal_name: Mapped[str] = mapped_column(String(80))
    contact_phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255))
    business_license_file_id: Mapped[int] = mapped_column(ID, ForeignKey("uploaded_files.id"))
    certification_status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Category(Record, Base):
    __tablename__ = "categories"
    parent_id: Mapped[int | None] = mapped_column(ID, ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(80))
    code: Mapped[str] = mapped_column(String(80), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class Product(Record, Base):
    __tablename__ = "products"
    category_id: Mapped[int] = mapped_column(ID, ForeignKey("categories.id"), index=True)
    created_by_merchant_id: Mapped[int] = mapped_column(ID, ForeignKey("merchant_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    brand: Mapped[str | None] = mapped_column(String(100))
    style: Mapped[str | None] = mapped_column(String(80))
    application_space: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class ProductSku(Record, Base):
    __tablename__ = "product_skus"
    product_id: Mapped[int] = mapped_column(ID, ForeignKey("products.id"), index=True)
    sku_code: Mapped[str] = mapped_column(String(80), unique=True)
    color: Mapped[str | None] = mapped_column(String(80))
    size_spec: Mapped[str | None] = mapped_column(String(120))
    material: Mapped[str | None] = mapped_column(String(120))
    power_watt: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    color_temperature: Mapped[str | None] = mapped_column(String(60))
    luminous_flux_lm: Mapped[int | None] = mapped_column(Integer)
    voltage: Mapped[str | None] = mapped_column(String(60))
    light_source_type: Mapped[str | None] = mapped_column(String(80))
    dimming_mode: Mapped[str | None] = mapped_column(String(100))
    installation_method: Mapped[str | None] = mapped_column(String(100))
    smart_protocol: Mapped[str | None] = mapped_column(String(100))
    extra_attributes: Mapped[dict | None] = mapped_column(JSON)
    reference_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class ProductImage(Record, Base):
    __tablename__ = "product_images"
    product_id: Mapped[int] = mapped_column(ID, ForeignKey("products.id"), index=True)
    sku_id: Mapped[int | None] = mapped_column(ID, ForeignKey("product_skus.id"))
    file_id: Mapped[int] = mapped_column(ID, ForeignKey("uploaded_files.id"), index=True)
    image_type: Mapped[str] = mapped_column(String(20), default="GALLERY")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class MerchantOffer(Record, Base):
    __tablename__ = "merchant_offers"
    __table_args__ = (
        CheckConstraint("price >= 0 AND stock_qty >= 0", name="ck_offers_values"),
        UniqueConstraint("merchant_id", "sku_id", "active_slot", name="uq_offer_active"),
        CheckConstraint("(status = 'ACTIVE' AND active_slot IS NOT NULL AND active_slot = 1) OR (status <> 'ACTIVE' AND active_slot IS NULL)", name="ck_offer_active_slot"),
    )
    merchant_id: Mapped[int] = mapped_column(ID, ForeignKey("merchant_profiles.id"), index=True)
    sku_id: Mapped[int] = mapped_column(ID, ForeignKey("product_skus.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    stock_qty: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(20), default="件")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active_slot: Mapped[int | None] = mapped_column(Integer)
    remark: Mapped[str | None] = mapped_column(String(500))
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class AuditRecord(Record):
    submitted_version: Mapped[int] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(500))
    auditor_user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id"))


class MerchantAudit(AuditRecord, Base):
    __tablename__ = "merchant_audits"
    merchant_id: Mapped[int] = mapped_column(ID, ForeignKey("merchant_profiles.id"), index=True)


class ProductAudit(AuditRecord, Base):
    __tablename__ = "product_audits"
    product_id: Mapped[int] = mapped_column(ID, ForeignKey("products.id"), index=True)


class OfferAudit(AuditRecord, Base):
    __tablename__ = "offer_audits"
    offer_id: Mapped[int] = mapped_column(ID, ForeignKey("merchant_offers.id"), index=True)


class OperationLog(Record, Base):
    __tablename__ = "operation_logs"
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    object_type: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[int] = mapped_column(ID)
    result: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    detail_json: Mapped[dict | None] = mapped_column(JSON)
