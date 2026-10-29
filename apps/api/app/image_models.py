from sqlalchemy import Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from .commerce_models import Record
from .database import Base


class ImageSearchLog(Record, Base):
    __tablename__ = "image_search_logs"
    query_id: Mapped[str] = mapped_column(String(36), unique=True)
    method: Mapped[str] = mapped_column(String(30))
    index_version: Mapped[str] = mapped_column(String(64))
    elapsed_ms: Mapped[float] = mapped_column(Float)
    requested_k: Mapped[int] = mapped_column(Integer)
    result_count: Mapped[int] = mapped_column(Integer)
    result_sku_ids: Mapped[list] = mapped_column(JSON)
