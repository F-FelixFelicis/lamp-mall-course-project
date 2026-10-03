"""M2 routes: controlled uploads and versioned merchant/catalog workflows."""

from datetime import datetime, timezone
from io import BytesIO
import hashlib
import uuid
import warnings

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from .commerce_models import Category, MerchantAudit, MerchantOffer, MerchantProfile, OfferAudit, OperationLog, Product, ProductAudit, ProductImage, ProductSku, UploadedFile
from .commerce_schemas import AuditRequest, MerchantApplication, OfferCreate, ProductCreate, ProductEdit, SaleRequest, SkuEdit, VersionRequest
from .commerce_schemas import AuditResult, CategoryResult, FileResult, MerchantResult, OfferResult, ProductPage, ProductResult
from .database import get_session
from .models import Role, User
from .security import bearer, get_current_user, require_role

router = APIRouter(prefix="/api/v1")


def fail(status: int, code: str, message: str):
    from .main import ApiError
    raise ApiError(status, code, message)


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def commit(session):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        fail(409, "DATA_CONFLICT", "编号重复或数据已变更，请刷新后重试")


def record(session, request, user, kind, obj_id, action, before=None, after=None):
    session.add(OperationLog(user_id=user.id, action=action, object_type=kind, object_id=obj_id,
        request_id=request.state.request_id, ip_address=request.client.host if request.client else None,
        detail_json={"before": before, "after": after}))


def merchant_for(session, user, approved=True):
    value = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id, MerchantProfile.deleted_at.is_(None)))
    if value is None or (approved and value.certification_status != "APPROVED"):
        fail(403, "MERCHANT_NOT_APPROVED", "请先完成商家认证")
    return value


def owned_product(session, user, product_id):
    merchant = merchant_for(session, user)
    value = session.get(Product, product_id)
    if value is None or value.deleted_at is not None or value.created_by_merchant_id != merchant.id:
        fail(404, "NOT_FOUND", "商品不存在")
    return value


def change(session, obj, version, states, **values):
    field = "certification_status" if isinstance(obj, MerchantProfile) else "status"
    model = type(obj)
    result = session.execute(update(model).where(model.id == obj.id, model.version == version,
        getattr(model, field).in_(states)).values(**values, version=model.version + 1).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        fail(409, "VERSION_CONFLICT", "状态或版本已变化，请刷新后重试")
    session.refresh(obj)


def audit_history(session, model, field, value):
    return [{"result": row.result, "reason": row.reason, "version": row.submitted_version, "created_at": row.created_at}
        for row in session.scalars(select(model).where(getattr(model, field) == value).order_by(model.id.desc())).all()]


def merchant_json(session, value):
    if value is None:
        return None
    return {key: getattr(value, key) for key in ("id", "shop_name", "legal_name", "contact_phone", "address",
        "business_license_file_id", "certification_status", "version")} | {
        "audits": audit_history(session, MerchantAudit, "merchant_id", value.id)}


def file_owned(session, file_id, user_id, purpose):
    value = session.get(UploadedFile, file_id)
    if not value or value.deleted_at or value.owner_user_id != user_id or value.purpose != purpose:
        fail(422, "INVALID_FILE", "请使用本人上传且用途正确的图片")
    return value


@router.post("/files", status_code=201, tags=["Files"], response_model=FileResult)
async def upload(request: Request, file: UploadFile = File(...), purpose: str = Form(...),
                 user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if purpose not in {"LICENSE", "PRODUCT"}:
        fail(422, "INVALID_PURPOSE", "图片用途必须为 LICENSE 或 PRODUCT")
    raw = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if len(raw) > 5 * 1024 * 1024:
        fail(413, "FILE_TOO_LARGE", "图片不能超过 5 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 20_000_000:
                    raise ValueError("unsupported image")
                source.load()
                output = BytesIO()
                source.convert("RGB").save(output, format="JPEG", quality=90)
                cleaned = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        fail(422, "INVALID_IMAGE", "请上传有效的 JPG、PNG 或 WebP 图片（不超过 2000 万像素）")
    folder = request.app.state.settings.upload_dir
    folder.mkdir(parents=True, exist_ok=True)
    key = uuid.uuid4().hex + ".jpg"
    target = folder / key
    target.write_bytes(cleaned)
    item = UploadedFile(owner_user_id=user.id, storage_key=key, original_name=(file.filename or "image")[:255],
        content_type="image/jpeg", size_bytes=len(cleaned), sha256=hashlib.sha256(cleaned).hexdigest(),
        access_level="PRIVATE", purpose=purpose)
    session.add(item)
    try:
        session.flush()
        record(session, request, user, "file", item.id, "UPLOAD")
        commit(session)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"id": item.id, "url": f"/api/v1/files/{item.id}/content", "purpose": purpose, "size_bytes": item.size_bytes}


@router.get("/files/{file_id}/content", tags=["Files"])
def file_content(file_id: int, request: Request, credentials=Depends(bearer), session: Session = Depends(get_session)):
    item = session.get(UploadedFile, file_id)
    if not item or item.deleted_at:
        fail(404, "NOT_FOUND", "图片不存在")
    public = item.purpose == "PRODUCT" and session.scalar(select(ProductImage.id).join(Product).join(Category).join(
        MerchantProfile, MerchantProfile.id == Product.created_by_merchant_id).join(User, User.id == MerchantProfile.user_id).where(ProductImage.file_id == file_id,
        Product.status == "ON_SALE", Product.deleted_at.is_(None), MerchantProfile.certification_status == "APPROVED",
        MerchantProfile.deleted_at.is_(None), Category.status == "ACTIVE", User.status == "ACTIVE", User.deleted_at.is_(None)).limit(1)) is not None
    if not public:
        user = get_current_user(request, credentials, session)
        if item.owner_user_id != user.id and "ADMIN" not in {r.code for r in user.roles}:
            fail(403, "FORBIDDEN", "无权访问此图片")
    target = request.app.state.settings.upload_dir / item.storage_key
    if not target.is_file():
        fail(404, "NOT_FOUND", "图片文件不存在")
    return FileResponse(target, media_type=item.content_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/categories", tags=["Catalog"], response_model=list[CategoryResult])
def categories(session: Session = Depends(get_session)):
    return [{"id": c.id, "name": c.name, "code": c.code} for c in session.scalars(
        select(Category).where(Category.status == "ACTIVE").order_by(Category.sort_order, Category.id))]


@router.get("/merchant/application", tags=["Merchant"], response_model=MerchantResult | None)
def get_application(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return merchant_json(session, session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id)))


@router.put("/merchant/application", tags=["Merchant"], response_model=MerchantResult)
def apply_merchant(payload: MerchantApplication, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    file_owned(session, payload.business_license_file_id, user.id, "LICENSE")
    value = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
    values = payload.model_dump(exclude={"version"})
    if value:
        change(session, value, payload.version, ["REJECTED"], **values, certification_status="PENDING")
    else:
        value = MerchantProfile(user_id=user.id, **values)
        session.add(value)
        try:
            session.flush()
        except IntegrityError:
            fail(409, "DATA_CONFLICT", "申请已存在，请刷新")
    if "MERCHANT" not in {r.code for r in user.roles}:
        role = session.scalar(select(Role).where(Role.code == "MERCHANT"))
        user.roles.append(role)
    record(session, request, user, "merchant", value.id, "SUBMIT_APPLICATION", after="PENDING")
    commit(session)
    return merchant_json(session, value)


def offer_json(session, offer):
    merchant = session.get(MerchantProfile, offer.merchant_id)
    sku = session.get(ProductSku, offer.sku_id)
    return {key: getattr(offer, key) for key in ("id", "merchant_id", "sku_id", "stock_qty", "unit", "status", "version", "remark")} | {
        "price": float(offer.price), "shop_name": merchant.shop_name, "sku_code": sku.sku_code,
        "product_name": session.get(Product, sku.product_id).name,
        "audits": audit_history(session, OfferAudit, "offer_id", offer.id)}


def active_offers():
    instant = now()
    return select(MerchantOffer).join(MerchantProfile).join(User, User.id == MerchantProfile.user_id).where(
        MerchantOffer.status == "ACTIVE", MerchantOffer.stock_qty > 0, MerchantOffer.effective_at <= instant,
        or_(MerchantOffer.expired_at.is_(None), MerchantOffer.expired_at > instant),
        MerchantProfile.certification_status == "APPROVED", MerchantProfile.deleted_at.is_(None),
        User.status == "ACTIVE", User.deleted_at.is_(None))


def product_json(session, product, public=False, merchant_id=None):
    result = {key: getattr(product, key) for key in ("id", "category_id", "name", "brand", "style", "application_space", "description", "status", "version")}
    result["category_name"] = session.get(Category, product.category_id).name
    result["skus"] = []
    prices = []
    for sku in session.scalars(select(ProductSku).where(ProductSku.product_id == product.id, ProductSku.status == "ACTIVE").order_by(ProductSku.id)):
        images = list(session.scalars(select(ProductImage).where(ProductImage.sku_id == sku.id).order_by(ProductImage.sort_order)))
        statement = active_offers().where(MerchantOffer.sku_id == sku.id) if public else select(MerchantOffer).where(MerchantOffer.sku_id == sku.id)
        if not public and merchant_id is not None:
            statement = statement.where(MerchantOffer.merchant_id == merchant_id)
        offers = [offer_json(session, o) for o in session.scalars(statement.order_by(MerchantOffer.price, MerchantOffer.id))]
        if public:
            for offer in offers:
                offer.pop("audits", None)
        prices.extend(o["price"] for o in offers if o["status"] == "ACTIVE" and o["stock_qty"] > 0)
        attributes = {key: getattr(sku, key) for key in ("color", "size_spec", "material", "power_watt", "color_temperature", "luminous_flux_lm")}
        result["skus"].append({"id": sku.id, "sku_code": sku.sku_code, "attributes": attributes,
            "image_file_ids": [i.file_id for i in images], "images": [f"/api/v1/files/{i.file_id}/content" for i in images], "offers": offers})
    result["cover_url"] = next((s["images"][0] for s in result["skus"] if s["images"]), None)
    result["lowest_price"] = min(prices) if prices else None
    if not public:
        result["audits"] = audit_history(session, ProductAudit, "product_id", product.id)
    return result


def market_statement():
    live = active_offers().with_only_columns(MerchantOffer.sku_id, MerchantOffer.price).subquery()
    prices = select(ProductSku.product_id, func.min(live.c.price).label("lowest_price")).join(live, live.c.sku_id == ProductSku.id).where(
        ProductSku.status == "ACTIVE").group_by(ProductSku.product_id).subquery()
    creator = aliased(MerchantProfile)
    return select(Product, prices.c.lowest_price).join(prices, prices.c.product_id == Product.id).join(Category).join(
        creator, creator.id == Product.created_by_merchant_id).join(User, User.id == creator.user_id).where(
        Product.status == "ON_SALE", Product.deleted_at.is_(None), Category.status == "ACTIVE",
        creator.certification_status == "APPROVED", creator.deleted_at.is_(None), User.status == "ACTIVE", User.deleted_at.is_(None))


@router.get("/products", tags=["Catalog"], response_model=ProductPage)
def products(keyword: str = Query(default="", max_length=100), category_id: int | None = None,
             sort: str = Query(default="newest", pattern="^(relevance|newest|price_asc|price_desc)$"),
             page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_session)):
    statement = market_statement()
    if keyword.strip():
        statement = statement.where(Product.name.contains(keyword.strip(), autoescape=True))
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    price = statement.selected_columns.lowest_price
    statement = statement.order_by(price.asc() if sort == "price_asc" else price.desc() if sort == "price_desc" else Product.id.desc(), Product.id)
    items = []
    for product, lowest in session.execute(statement.offset((page - 1) * page_size).limit(page_size)):
        data = product_json(session, product, public=True)
        items.append({key: data[key] for key in ("id", "name", "category_name", "cover_url", "lowest_price", "status")})
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.get("/products/{product_id}", tags=["Catalog"], response_model=ProductResult, response_model_exclude_none=True)
def product_detail(product_id: int, session: Session = Depends(get_session)):
    product = session.scalar(market_statement().where(Product.id == product_id))
    if product is None:
        fail(404, "NOT_FOUND", "商品暂无有效报价或已下架")
    return product_json(session, product, public=True)


@router.get("/merchant/products", tags=["Merchant"], response_model=list[ProductResult])
def my_products(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    merchant = merchant_for(session, user, approved=False)
    return [product_json(session, p, merchant_id=merchant.id) for p in session.scalars(select(Product).where(
        Product.created_by_merchant_id == merchant.id, Product.deleted_at.is_(None)).order_by(Product.id.desc()))]


def check_category(session, category_id):
    value = session.get(Category, category_id)
    if not value or value.status != "ACTIVE":
        fail(422, "INVALID_CATEGORY", "请选择有效分类")


def add_images(session, user, product_id, sku_id, file_ids):
    for order, file_id in enumerate(dict.fromkeys(file_ids)):
        file_owned(session, file_id, user.id, "PRODUCT")
        session.add(ProductImage(product_id=product_id, sku_id=sku_id, file_id=file_id, sort_order=order))


@router.post("/merchant/products", status_code=201, tags=["Merchant"], response_model=ProductResult)
def create_product(payload: ProductCreate, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    merchant = merchant_for(session, user)
    check_category(session, payload.category_id)
    product = Product(created_by_merchant_id=merchant.id, **payload.model_dump(exclude={"skus"}))
    session.add(product)
    try:
        session.flush()
        for entry in payload.skus:
            sku = ProductSku(product_id=product.id, **entry.model_dump(exclude={"image_file_ids"}))
            session.add(sku)
            session.flush()
            add_images(session, user, product.id, sku.id, entry.image_file_ids)
    except IntegrityError:
        fail(409, "SKU_EXISTS", "SKU 编码已存在，请使用新的编码")
    record(session, request, user, "product", product.id, "CREATE", after="DRAFT")
    commit(session)
    return product_json(session, product, merchant_id=merchant.id)


@router.put("/merchant/products/{product_id}", tags=["Merchant"], response_model=ProductResult)
def edit_product(product_id: int, payload: ProductEdit, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    product = owned_product(session, user, product_id)
    check_category(session, payload.category_id)
    change(session, product, payload.version, ["DRAFT", "REJECTED", "OFF_SALE"], **payload.model_dump(exclude={"version"}), status="DRAFT")
    record(session, request, user, "product", product.id, "EDIT", after="DRAFT")
    commit(session)
    return product_json(session, product, merchant_id=product.created_by_merchant_id)


@router.put("/merchant/skus/{sku_id}", tags=["Merchant"], response_model=ProductResult)
def edit_sku(sku_id: int, payload: SkuEdit, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    sku = session.get(ProductSku, sku_id)
    if not sku:
        fail(404, "NOT_FOUND", "规格不存在")
    product = owned_product(session, user, sku.product_id)
    change(session, product, payload.version, ["DRAFT", "REJECTED", "OFF_SALE"], status="DRAFT")
    for key, value in payload.model_dump(exclude={"version", "image_file_ids"}).items():
        setattr(sku, key, value)
    session.execute(delete(ProductImage).where(ProductImage.sku_id == sku_id))
    add_images(session, user, product.id, sku.id, payload.image_file_ids)
    # A changed specification invalidates previously reviewed prices.
    session.execute(update(MerchantOffer).where(MerchantOffer.sku_id == sku_id, MerchantOffer.status.in_(["ACTIVE", "PENDING", "DRAFT"])).values(
        status="EXPIRED", active_slot=None, expired_at=now(), version=MerchantOffer.version + 1))
    record(session, request, user, "product", product.id, "EDIT_SKU", after="DRAFT")
    commit(session)
    return product_json(session, product, merchant_id=product.created_by_merchant_id)


@router.post("/merchant/products/{product_id}/submit", status_code=202, tags=["Merchant"], response_model=ProductResult)
def submit_product(product_id: int, payload: VersionRequest, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    product = owned_product(session, user, product_id)
    change(session, product, payload.version, ["DRAFT", "REJECTED", "OFF_SALE"], status="PENDING")
    record(session, request, user, "product", product.id, "SUBMIT", after="PENDING")
    commit(session)
    return product_json(session, product, merchant_id=product.created_by_merchant_id)


@router.post("/merchant/products/{product_id}/sale", tags=["Merchant"], response_model=ProductResult)
def sale_product(product_id: int, payload: SaleRequest, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    product = owned_product(session, user, product_id)
    target = "ON_SALE" if payload.on_sale else "OFF_SALE"
    change(session, product, payload.version, ["APPROVED", "OFF_SALE"] if payload.on_sale else ["ON_SALE"], status=target)
    record(session, request, user, "product", product.id, "SALE", after=target)
    commit(session)
    return product_json(session, product, merchant_id=product.created_by_merchant_id)


@router.post("/merchant/skus/{sku_id}/offers", status_code=201, tags=["Merchant"], response_model=OfferResult)
def create_offer(sku_id: int, payload: OfferCreate, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    merchant = merchant_for(session, user)
    sku = session.get(ProductSku, sku_id)
    product = session.get(Product, sku.product_id) if sku else None
    if not product or product.status not in {"APPROVED", "ON_SALE", "OFF_SALE"} or sku.status != "ACTIVE" or product.deleted_at:
        fail(409, "PRODUCT_NOT_APPROVED", "请先通过商品审核再创建报价")
    offer = MerchantOffer(merchant_id=merchant.id, sku_id=sku_id, **payload.model_dump())
    session.add(offer)
    session.flush()
    record(session, request, user, "offer", offer.id, "CREATE", after="DRAFT")
    commit(session)
    return offer_json(session, offer)


@router.get("/merchant/offers", tags=["Merchant"], response_model=list[OfferResult])
def my_offers(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    merchant = merchant_for(session, user, approved=False)
    return [offer_json(session, o) for o in session.scalars(select(MerchantOffer).where(MerchantOffer.merchant_id == merchant.id).order_by(MerchantOffer.id.desc()))]


@router.post("/merchant/offers/{offer_id}/submit", status_code=202, tags=["Merchant"], response_model=OfferResult)
def submit_offer(offer_id: int, payload: VersionRequest, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    merchant = merchant_for(session, user)
    offer = session.get(MerchantOffer, offer_id)
    if not offer or offer.merchant_id != merchant.id:
        fail(404, "NOT_FOUND", "报价不存在")
    sku = session.get(ProductSku, offer.sku_id)
    if session.get(Product, sku.product_id).status not in {"APPROVED", "ON_SALE", "OFF_SALE"}:
        fail(409, "PRODUCT_NOT_APPROVED", "商品未通过审核")
    change(session, offer, payload.version, ["DRAFT"], status="PENDING")
    record(session, request, user, "offer", offer.id, "SUBMIT", after="PENDING")
    commit(session)
    return offer_json(session, offer)


@router.get("/admin/merchants", tags=["Admin"], response_model=list[MerchantResult])
def admin_merchants(user: User = Depends(require_role("ADMIN")), session: Session = Depends(get_session)):
    return [merchant_json(session, m) for m in session.scalars(select(MerchantProfile).order_by(MerchantProfile.id.desc()))]


@router.get("/admin/products", tags=["Admin"], response_model=list[ProductResult])
def admin_products(user: User = Depends(require_role("ADMIN")), session: Session = Depends(get_session)):
    return [product_json(session, p) for p in session.scalars(select(Product).where(Product.deleted_at.is_(None)).order_by(Product.id.desc()))]


@router.get("/admin/offers", tags=["Admin"], response_model=list[OfferResult])
def admin_offers(user: User = Depends(require_role("ADMIN")), session: Session = Depends(get_session)):
    return [offer_json(session, o) for o in session.scalars(select(MerchantOffer).order_by(MerchantOffer.id.desc()))]


@router.post("/admin/{kind}/{object_id}/audit", tags=["Admin"], response_model=AuditResult)
def audit(kind: str, object_id: int, payload: AuditRequest, request: Request,
          user: User = Depends(require_role("ADMIN")), session: Session = Depends(get_session)):
    config = {"merchants": (MerchantProfile, MerchantAudit, "merchant_id", "certification_status"),
              "products": (Product, ProductAudit, "product_id", "status"),
              "offers": (MerchantOffer, OfferAudit, "offer_id", "status")}
    if kind not in config:
        fail(404, "NOT_FOUND", "审核对象不存在")
    model, audit_model, foreign_key, status_field = config[kind]
    obj = session.get(model, object_id)
    if obj is None:
        fail(404, "NOT_FOUND", "审核对象不存在")
    existing = session.scalar(select(audit_model).where(getattr(audit_model, foreign_key) == object_id,
        audit_model.submitted_version == payload.version))
    if existing:
        if existing.result != payload.result or (existing.reason or "") != payload.reason:
            fail(409, "AUDIT_CONFLICT", "此版本已审核，请刷新")
        return {"id": obj.id, "status": getattr(obj, status_field), "version": obj.version}
    values = {status_field: payload.result}
    if isinstance(obj, (Product, MerchantOffer)):
        owner_id = obj.created_by_merchant_id if isinstance(obj, Product) else obj.merchant_id
        owner = session.get(MerchantProfile, owner_id)
        if owner.certification_status != "APPROVED":
            fail(409, "MERCHANT_NOT_APPROVED", "商家尚未通过认证")
    if isinstance(obj, MerchantOffer) and payload.result == "APPROVED":
        sku = session.get(ProductSku, obj.sku_id)
        if session.get(Product, sku.product_id).status not in {"APPROVED", "ON_SALE", "OFF_SALE"}:
            fail(409, "PRODUCT_NOT_APPROVED", "商品尚未通过审核")
        # The unique active_slot constraint is the final arbiter under concurrent approvals.
        session.execute(update(MerchantOffer).where(MerchantOffer.merchant_id == obj.merchant_id,
            MerchantOffer.sku_id == obj.sku_id, MerchantOffer.status == "ACTIVE").values(
                status="EXPIRED", active_slot=None, expired_at=now(), version=MerchantOffer.version + 1))
        values.update(status="ACTIVE", active_slot=1, effective_at=now())
    change(session, obj, payload.version, ["PENDING"], **values)
    session.add(audit_model(**{foreign_key: object_id}, submitted_version=payload.version,
        result=payload.result, reason=payload.reason, auditor_user_id=user.id))
    record(session, request, user, kind, object_id, "AUDIT", before="PENDING", after=getattr(obj, status_field))
    commit(session)
    return {"id": obj.id, "status": getattr(obj, status_field), "version": obj.version}
