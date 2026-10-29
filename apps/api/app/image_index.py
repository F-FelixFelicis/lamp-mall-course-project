"""Atomic, versioned local image index; DB saleability is checked at query time."""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import threading
import uuid

import numpy as np
from sqlalchemy import select

from .commerce import market_statement
from .commerce_models import ProductImage, ProductSku, UploadedFile
from .image_features import COLOR_VERSION, DEEP_VERSION, ResnetEncoder, SearchUnavailable, color_vector, decode_image


def eligible_images(session):
    # Preserve the catalogue's current merchant/category/offer eligibility joins.
    market = market_statement().subquery()
    rows = session.execute(select(ProductSku, ProductImage, UploadedFile).join(ProductImage, ProductImage.sku_id == ProductSku.id)
        .join(UploadedFile, UploadedFile.id == ProductImage.file_id).where(ProductSku.product_id.in_(select(market.c.id)),
            ProductSku.status == "ACTIVE", UploadedFile.purpose == "PRODUCT", UploadedFile.deleted_at.is_(None))
        .order_by(ProductSku.id, ProductImage.id)).all()
    return [{"sku_id":s.id, "product_id":s.product_id, "file_id":f.id, "sha256":f.sha256,
        "storage_key":f.storage_key} for s, _, f in rows]


def source_signature(rows):
    clean = [{k:r[k] for k in ("sku_id","product_id","file_id","sha256")} for r in rows]
    return sha256(json.dumps(clean,sort_keys=True,separators=(",",":")).encode()).hexdigest()


class ImageIndex:
    def __init__(self, settings):
        self.folder = settings.upload_dir.parent / "image-search"
        self.path = self.folder / "index.npz"
        self.upload_dir = settings.upload_dir
        self.weights_path = settings.image_model_path
        self._encoder = None
        self._encoder_lock = threading.Lock()
        self._build_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._cache = None
        self._cache_stamp = None

    def encoder(self):
        with self._encoder_lock:
            if self._encoder is None:
                self._encoder = ResnetEncoder(self.weights_path)
            return self._encoder

    def load(self):
        if not self.path.is_file():
            raise SearchUnavailable("商品图索引尚未建立，请联系管理员建立索引")
        with self._cache_lock:
            stat = self.path.stat()
            stamp = (stat.st_mtime_ns,stat.st_size)
            if self._cache_stamp != stamp:
                try:
                    with np.load(self.path, allow_pickle=False) as data:
                        meta = json.loads(str(data["metadata"].item()))
                        deep, color = data["deep"].copy(), data["color"].copy()
                    rows = meta["rows"]
                    if meta["deep_version"] != DEEP_VERSION or meta["color_version"] != COLOR_VERSION:
                        raise ValueError("algorithm mismatch")
                    if deep.shape != (len(rows),512) or color.shape != (len(rows),128):
                        raise ValueError("dimension mismatch")
                    if not np.isfinite(deep).all() or not np.isfinite(color).all():
                        raise ValueError("nonfinite index")
                    self._cache = (meta,deep,color)
                    self._cache_stamp = stamp
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise SearchUnavailable("商品图索引损坏或版本不兼容，请重新建立索引") from exc
            return self._cache

    def build(self, session):
        if not self._build_lock.acquire(blocking=False):
            raise SearchUnavailable("索引正在建立，请稍后刷新状态")
        try:
            rows = eligible_images(session)
            if len(rows) > 5000:
                raise SearchUnavailable("当前演示索引最多处理 5000 张商品图，请先缩小图库")
            encoder = self.encoder()
            deep, color = [], []
            for row in rows:
                path = (self.upload_dir / row["storage_key"]).resolve()
                if path.parent != self.upload_dir.resolve() or not path.is_file():
                    raise SearchUnavailable(f"商品图片 {row['file_id']} 缺失，原索引保留")
                raw = path.read_bytes()
                if sha256(raw).hexdigest() != row["sha256"]:
                    raise SearchUnavailable(f"商品图片 {row['file_id']} 校验失败，原索引保留")
                image = decode_image(raw)
                deep.append(encoder.encode(image))
                color.append(color_vector(image))
            source_hash = source_signature(rows)
            meta = {"rows":rows,"source_signature":source_hash,"deep_version":DEEP_VERSION,
                "color_version":COLOR_VERSION,"weights_sha256":encoder.weights_sha256,
                "runtime":encoder.runtime,"created_at":datetime.now(timezone.utc).isoformat()}
            meta["index_version"] = sha256((source_hash+DEEP_VERSION+COLOR_VERSION+encoder.weights_sha256).encode()).hexdigest()
            vectors = np.asarray(deep,dtype=np.float32).reshape((-1,512))
            baseline = np.asarray(color,dtype=np.float32).reshape((-1,128))
            self.folder.mkdir(parents=True,exist_ok=True)
            temp = self.folder / (uuid.uuid4().hex+".tmp")
            try:
                with temp.open("wb") as out:
                    np.savez_compressed(out,metadata=json.dumps(meta,ensure_ascii=False),deep=vectors,color=baseline)
                temp.replace(self.path)
            finally:
                temp.unlink(missing_ok=True)
            with self._cache_lock:
                self._cache_stamp = None
            return meta
        finally:
            self._build_lock.release()

    def status(self, session):
        live = eligible_images(session)
        base = {"eligible_images":len(live),"weights_ready":self.weights_path.is_file(),
            "model_preloaded":self._encoder is not None,
            "dependencies_ready":all(importlib.util.find_spec(x) is not None for x in ("torch","torchvision")),
            "query_images_retained":False}
        try:
            meta,_,_ = self.load()
        except SearchUnavailable as exc:
            return base | {"ready":False,"message":str(exc),"needs_rebuild":True,"indexed_images":0,"indexed_skus":0}
        return base | {"ready":True,"message":"索引已就绪", "needs_rebuild":meta["source_signature"] != source_signature(live),
            "indexed_images":len(meta["rows"]),"indexed_skus":len({r["sku_id"] for r in meta["rows"]}),
            **{k:meta[k] for k in ("index_version","created_at","deep_version","color_version","weights_sha256")}}

    def rank(self, image, method, eligible):
        meta,deep,color = self.load()
        if method == "deep":
            encoder = self.encoder()
            if encoder.weights_sha256 != meta["weights_sha256"]:
                raise SearchUnavailable("模型权重与索引不一致，请重新建立索引")
            vector, matrix = encoder.encode(image),deep
        else:
            vector, matrix = color_vector(image),color
        scores = matrix @ vector
        # Revalidate both live business state and current SKU/image association.
        live_keys = {(r["sku_id"],r["file_id"],r["sha256"]) for r in eligible
            if (self.upload_dir/r["storage_key"]).resolve().parent == self.upload_dir.resolve()
            and (self.upload_dir/r["storage_key"]).is_file()}
        best = {}
        for row,score in zip(meta["rows"],scores):
            if (row["sku_id"],row["file_id"],row["sha256"]) not in live_keys:
                continue
            entry = row | {"score":float(np.clip(score,-1,1))}
            if row["sku_id"] not in best or entry["score"] > best[row["sku_id"]]["score"]:
                best[row["sku_id"]] = entry
        return meta,sorted(best.values(),key=lambda r:(-r["score"],r["sku_id"],r["file_id"]))
