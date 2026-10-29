"""Bounded multipart image queries and admin index operations."""
from datetime import datetime
import time
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .commerce import commit, fail, product_json, record
from .commerce_models import Product
from .database import get_session
from .image_features import MAX_BYTES, ImageInputError, SearchUnavailable, decode_image
from .image_index import ImageIndex, eligible_images
from .image_models import ImageSearchLog
from .models import User
from .security import require_role

router = APIRouter(prefix="/api/v1", tags=["Image Search"])


class SimilarItem(BaseModel):
    sku_id: int
    product_id: int
    product_name: str
    sku_code: str
    category_name: str
    matched_image_url: str
    lowest_price: float
    is_demo: bool
    score: float


class SearchResult(BaseModel):
    query_id: str
    method: str
    index_version: str
    algorithm_version: str
    elapsed_ms: float
    items: list[SimilarItem]
    warning: str


class SearchLogResult(BaseModel):
    query_id: str
    method: str
    index_version: str
    elapsed_ms: float
    requested_k: int
    result_count: int
    result_sku_ids: list[int]
    created_at: datetime


def service(request):
    return request.app.state.image_index


@router.post("/search/image", response_model=SearchResult)
def search_image(request: Request, file: UploadFile = File(...), k: int = Form(5, ge=1, le=20),
        method: Literal["deep", "color"] = Form("deep"), category_id: int | None = Form(None, gt=0),
        session: Session = Depends(get_session)):
    started = time.perf_counter()
    query_id = str(uuid.uuid4())
    try:
        raw = file.file.read(MAX_BYTES+1)
        image = decode_image(raw)
        del raw
        eligible = eligible_images(session)
        index = service(request)
        meta,ranked = index.rank(image,method,eligible)
        output,products = [],{}
        for entry in ranked:
            pid = entry["product_id"]
            if pid not in products:
                products[pid] = product_json(session,session.get(Product,pid),public=True)
            product = products[pid]
            if category_id is not None and product["category_id"] != category_id:
                continue
            sku = next((s for s in product["skus"] if s["id"] == entry["sku_id"]), None)
            if not sku or not sku["offers"]:
                continue
            output.append({"sku_id":sku["id"],"product_id":pid,"product_name":product["name"],"sku_code":sku["sku_code"],
                "category_name":product["category_name"],"matched_image_url":f"/api/v1/files/{entry['file_id']}/content",
                "lowest_price":min(o["price"] for o in sku["offers"]),"is_demo":product["is_demo"],"score":round(entry["score"],6)})
            if len(output) >= k:
                break
        elapsed = round((time.perf_counter()-started)*1000,3)
        session.add(ImageSearchLog(query_id=query_id,method=method,index_version=meta["index_version"],
            elapsed_ms=elapsed,requested_k=k,result_count=len(output),result_sku_ids=[x["sku_id"] for x in output]))
        commit(session)
        warning = "结果为视觉相似候选，分数不是同款概率；若不相关，请裁剪至单盏灯后重试。"
        if not output:
            warning = "暂无当前可购买的相似候选，可更换图片或使用文字搜索。"
        return {"query_id":query_id,"method":method,"index_version":meta["index_version"],
            "algorithm_version":meta["deep_version" if method == "deep" else "color_version"],
            "elapsed_ms":elapsed,"items":output,"warning":warning}
    except ImageInputError as exc:
        fail(exc.status,exc.code,exc.message)
    except SearchUnavailable as exc:
        fail(503,"IMAGE_SEARCH_UNAVAILABLE",str(exc))
    finally:
        file.file.close()


@router.get("/admin/image-search/status")
def status(request: Request, user: User = Depends(require_role("ADMIN")), session: Session = Depends(get_session)):
    return service(request).status(session)


@router.post("/admin/image-search/index")
def build_index(request: Request, user: User = Depends(require_role("ADMIN")), session: Session = Depends(get_session)):
    try:
        index = service(request)
        meta = index.build(session)
        record(session,request,user,"image_index",0,"REBUILD",after=meta["index_version"])
        commit(session)
        return index.status(session)
    except (SearchUnavailable, ImageInputError) as exc:
        fail(503,"IMAGE_SEARCH_UNAVAILABLE",str(exc) if isinstance(exc,SearchUnavailable) else exc.message)


@router.get("/admin/image-search/logs", response_model=list[SearchLogResult])
def recent_logs(user: User = Depends(require_role("ADMIN")), session: Session = Depends(get_session)):
    return [{k:getattr(row,k) for k in ("query_id","method","index_version","elapsed_ms","requested_k","result_count","result_sku_ids","created_at")}
        for row in session.scalars(select(ImageSearchLog).order_by(ImageSearchLog.id.desc()).limit(20))]
