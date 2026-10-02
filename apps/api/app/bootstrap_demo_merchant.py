"""Create a local-only merchant identity for M1 screen testing."""

import argparse
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .config import Settings
from .database import make_engine
from .models import Role, User
from .security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local demo merchant login")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    settings = Settings.from_env()
    if settings.app_env != "local":
        raise SystemExit("Demo merchant creation is local-only")
    password = getpass("Merchant password: ")
    if len(password) < 8:
        raise SystemExit("Password must contain at least 8 characters")
    session_factory = sessionmaker(bind=make_engine(settings.database_url))
    with session_factory.begin() as session:
        if session.scalar(select(User.id).where(User.username == args.username)) is not None:
            raise SystemExit("Username already exists")
        role = session.scalar(select(Role).where(Role.code == "MERCHANT"))
        if role is None:
            raise SystemExit("Run alembic upgrade head first")
        session.add(User(username=args.username, password_hash=hash_password(password), display_name=args.username, roles=[role]))
    print("Local demo merchant created; certification workflow is implemented in M2")


if __name__ == "__main__":
    main()

