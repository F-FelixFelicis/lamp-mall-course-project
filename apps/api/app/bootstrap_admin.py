"""Create the first administrator after applying migrations."""

import argparse
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .config import Settings
from .database import make_engine
from .models import Role, User
from .security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an administrator account")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    password = getpass("Administrator password: ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    engine = make_engine(Settings.from_env().database_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory.begin() as session:
        if session.scalar(select(User.id).where(User.username == args.username)) is not None:
            raise SystemExit("Username already exists; no role was changed")
        role = session.scalar(select(Role).where(Role.code == "ADMIN"))
        if role is None:
            raise SystemExit("Run alembic upgrade head first")
        session.add(User(username=args.username, password_hash=hash_password(password), display_name=args.username, roles=[role]))
    print("Administrator created")


if __name__ == "__main__":
    main()

