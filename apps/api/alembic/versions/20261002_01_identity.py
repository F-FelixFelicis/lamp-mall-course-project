"""M1 account and role tables

Revision ID: 20261002_01
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


IDENTITY_TYPE = sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql").with_variant(sa.Integer(), "sqlite")


revision = "20261002_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", IDENTITY_TYPE, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), unique=True, nullable=True),
        sa.Column("phone", sa.String(20), unique=True, nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("username IS NOT NULL OR phone IS NOT NULL", name="ck_users_identity"),
    )
    op.create_index("idx_users_status", "users", ["status"])
    op.create_table(
        "roles",
        sa.Column("id", IDENTITY_TYPE, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(40), unique=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", IDENTITY_TYPE, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", IDENTITY_TYPE, sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )
    roles = sa.table("roles", sa.column("code", sa.String), sa.column("name", sa.String))
    op.bulk_insert(roles, [{"code": "CUSTOMER", "name": "客户"}, {"code": "MERCHANT", "name": "商家"}, {"code": "ADMIN", "name": "管理员"}])


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_index("idx_users_status", table_name="users")
    op.drop_table("users")
