"""M1 identity tables. Later migrations add the remaining commerce tables."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_status", "status"),
        CheckConstraint("username IS NOT NULL OR phone IS NOT NULL", name="ck_users_identity"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime())

    roles: Mapped[list["Role"]] = relationship(secondary="user_roles", lazy="selectin")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.current_timestamp())


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite"), ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite"), ForeignKey("roles.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.current_timestamp())
