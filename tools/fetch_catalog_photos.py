"""Fetch the explicitly curated licensed photos for the demo catalog (no crawling)."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "assets" / "catalog" / "catalog.json"

def fetch(row):
    photo = row["photo"]
    photo_id = row["sku_code"]
    target = ROOT / "assets" / "catalog" / photo["file"]
    if target.exists():
        return f"{photo_id}: already present"
    # Preserve the complete frame; CDN resizing only, no generated or retouched content.
    url = photo["download"]
    if sys.platform == "win32":
        # Windows trust store; allow offline CRL endpoints, retain certificate validation.
        content = subprocess.check_output(["curl.exe", "--fail", "--silent", "--show-error", "--ssl-revoke-best-effort", "--retry", "2", "--max-time", "45", url])
    else:
        with urlopen(Request(url, headers={"User-Agent": "LampMallCourseDemo/1.0"}), timeout=45) as response:
            content = response.read(5 * 1024 * 1024 + 1)
    if not content.startswith(b"\xff\xd8") or len(content) > 5 * 1024 * 1024:
        raise ValueError(f"Unexpected image response: {photo_id}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return f"{photo_id}: {len(content)} bytes"

if __name__ == "__main__":
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]
    with ThreadPoolExecutor(max_workers=4) as executor:
        for result in executor.map(fetch, rows):
            print(result)
