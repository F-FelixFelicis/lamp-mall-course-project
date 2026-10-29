"""Back up the default local SQLite database before applying M3 migrations."""
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps/api"
DB = API / ".local/lamp_mall.db"
url = f"sqlite:///{DB.as_posix()}"
if os.getenv("APP_ENV", "local") != "local" or os.getenv("DATABASE_URL", url) != url:
    raise SystemExit("Only the default local SQLite database is supported")
if not DB.is_file():
    raise SystemExit("Local database does not exist; run alembic upgrade head for a new database")

def counts(connection):
    return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("users", "products", "merchant_offers")}

folder = API / ".local/backups"
folder.mkdir(parents=True, exist_ok=True)
backup = folder / f"before-m3-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
with sqlite3.connect(DB) as source, sqlite3.connect(backup) as target:
    before = counts(source)
    source.backup(target)
    if counts(target) != before or target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("Backup verification failed; migration not started")
print(f"Verified backup: {backup}")
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=API,
    env=os.environ | {"DATABASE_URL":url}, check=True)
with sqlite3.connect(DB) as connection:
    if counts(connection) != before:
        raise SystemExit("Existing record counts changed; inspect database and backup")
    print(f"Existing records preserved: {before}")
    print("Revision:", connection.execute("SELECT version_num FROM alembic_version").fetchone()[0])
