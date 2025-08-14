# --- top of file ---
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any  # <-- use typing for 3.8
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparse
import yaml

# zoneinfo with fallback for Python < 3.9
try:
    from zoneinfo import ZoneInfo  # 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # 3.8

OUTPUT_DIR = Path("docs/news")
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_config(path: Path) -> List[Dict[str, Any]]:   # <-- typing.List[...] instead of list[...]
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("sources", [])

def parse_ts(entry: Dict[str, Any]) -> datetime:
    for key in ("published", "pubDate", "updated"):
        v = entry.get(key)
        if v:
            try:
                return dtparse.parse(v).astimezone(timezone.utc)
            except Exception:
                pass
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def image_from_description(desc: Optional[str]) -> Optional[str]:
    if not desc:
        return None
    soup = BeautifulSoup(desc, "lxml")
    img = soup.find("img")
    return img["src"].strip() if img and img.get("src") else None

def today_filename() -> Path:
    # Vietnam-local date for filename
    today_local = datetime.now(TIMEZONE)
    return OUTPUT_DIR / f"{today_local.strftime('%m-%d-%Y')}.json"

def load_day(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}

def save_day(path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    items = list(data.values())
    items.sort(key=lambda x: x.get("published", ""), reverse=True)
    path.write_text(
        json.dumps({i["item_id"]: i for i in items}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def crawl(config_path: str = "config.yaml") -> None:
    feeds = load_config(Path(config_path))
    out_path = today_filename()
    existing = load_day(out_path)
    seen_ids = set(existing.keys())
    added = 0

    for feed in feeds:
        source = feed["name"]
        urls: List[str] = feed.get("urls", [])
        for url in urls:
            parsed = feedparser.parse(url)
            for e in parsed.entries:
                guid = (e.get("id") or e.get("guid") or e.get("link") or "").strip()
                link = (e.get("link") or "").strip()
                title = (e.get("title") or "").strip()
                published = parse_ts(e)
                image = image_from_description(e.get("description"))

                item_id = sha1(guid or link or (source + title + published.isoformat()))
                if item_id in seen_ids:
                    continue

                existing[item_id] = {
                    "item_id": item_id,
                    "source": source,
                    "title": title,
                    "link": link,
                    "guid": guid or link,
                    "image": image,
                    "published": published.isoformat(),
                }
                seen_ids.add(item_id)
                added += 1

    save_day(out_path, existing)
    print(f"Saved: {out_path} (+{added} new items, total {len(existing)})")

if __name__ == "__main__":
    crawl()
