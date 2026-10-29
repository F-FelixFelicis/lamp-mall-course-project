"""Fetch a small, source-traceable set of lamp query-photo candidates.

The photo list was curated from Pexels photo pages. These are *query candidates*,
not labeled retrieval ground truth. Review visibility and annotate relevance
to each catalog SKU before using them for Recall@5/Precision@5.
"""

from __future__ import annotations

from datetime import date
import hashlib
import io
import json
from pathlib import Path
import subprocess

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "image_search_queries"
LICENSE_URL = "https://www.pexels.com/license/"

# (photo ID, preliminary class, photographer, source photo page)
PHOTOS = [
    (27781350, "TABLE", "Wo Nfoni Media", "https://www.pexels.com/photo/a-lamp-with-a-white-shade-on-top-of-a-table-27781350/"),
    (8834624, "TABLE", "Ron Lach", "https://www.pexels.com/photo/a-table-lamp-on-the-table-with-mirror-8834624/"),
    (19240054, "TABLE", "juliane Monari", "https://www.pexels.com/photo/black-and-white-photo-of-a-desk-lamp-19240054/"),
    (37412550, "PENDANT", "Jonathan Córdova R.", "https://www.pexels.com/photo/modern-pendant-lamp-with-warm-light-indoors-37412550/"),
    (8763072, "PENDANT", "Pavel Danilyuk", "https://www.pexels.com/photo/pendant-lamp-above-a-table-8763072/"),
    (221151, "PENDANT", "Jens", "https://www.pexels.com/photo/brown-pendant-lamp-during-nighttime-221151/"),
    (26346242, "FLOOR", "Ozge Alpaslan", "https://www.pexels.com/photo/lamp-in-room-corner-26346242/"),
    (19934344, "FLOOR", "Bruna Crossi", "https://www.pexels.com/photo/black-lamp-on-white-background-19934344/"),
    (3987481, "FLOOR", "Lucian Petrean", "https://www.pexels.com/photo/black-floor-lamp-beside-gray-couch-3987481/"),
    (15970989, "WALL", "Benjamin Farren", "https://www.pexels.com/photo/a-lamp-shining-in-the-darkness-15970989/"),
    (28446048, "WALL", "Jan van der Wolf", "https://www.pexels.com/photo/minimalist-white-wall-with-lamp-and-plant-28446048/"),
    (16241146, "WALL", "Fatih Doğrul", "https://www.pexels.com/photo/lamp-on-wall-16241146/"),
    (6980702, "CEILING", "Max Vakhtbovych", "https://www.pexels.com/photo/modern-chandelier-hanging-on-ceiling-at-home-6980702/"),
    (28656089, "CEILING", "Melbin Jacob", "https://www.pexels.com/photo/elegant-vintage-ceiling-light-fixture-in-dim-room-28656089/"),
    (5990394, "CEILING", "Sonny Sixteen", "https://www.pexels.com/photo/modern-chandelier-5990394/"),
]


def download(url: str) -> bytes:
    return subprocess.check_output([
        "curl.exe", "--fail", "--silent", "--show-error", "--location",
        "--ssl-revoke-best-effort", "--retry", "2", "--max-time", "40", url,
    ])


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    existing_gallery_ids = {
        int(path.stem.split("-")[-1])
        for path in (ROOT / "assets" / "catalog").glob("pexels-*.jpg")
    }
    for photo_id, category, artist, page in PHOTOS:
        if photo_id in existing_gallery_ids:
            raise ValueError(f"Query image duplicates gallery source ID: {photo_id}")
        name = f"pexels-query-{photo_id}.jpg"
        target = OUTPUT / name
        url = (
            f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
            "?auto=compress&cs=tinysrgb&w=1000&h=1000&fit=max"
        )
        if not target.exists():
            data = download(url)
            if not data.startswith(b"\xff\xd8") or len(data) > 5_000_000:
                raise ValueError(f"Unexpected image response for {photo_id}")
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            target.write_bytes(data)
        data = target.read_bytes()
        with Image.open(target) as image:
            width, height = image.size
        rows.append({
            "id": f"Q-{photo_id}",
            "file": name,
            "source_photo_id": photo_id,
            "source_page": page,
            "download_url": url,
            "photographer": artist,
            "license": "Pexels License",
            "license_url": LICENSE_URL,
            "preliminary_category": category,
            "relevance_to_catalog_skus": None,
            "review_status": "category_candidate_only",
            "width": width,
            "height": height,
            "sha256": hashlib.sha256(data).hexdigest(),
        })
        print(name, width, height)
    (OUTPUT / "manifest.json").write_text(
        json.dumps({"collection_date": date.today().isoformat(), "role": "image_search_query_candidates", "images": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("total", len(rows))


if __name__ == "__main__":
    main()
