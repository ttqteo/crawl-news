import hashlib, json, os
from scripts.build_index import build_index
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any  # <-- use typing for 3.8
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparse
import yaml
from parsers import get_parser, FeedContext

try:
    from zoneinfo import ZoneInfo  # python >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo  # python < 3.9

OUTPUT_DIR = Path("public/news")
TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_config(path: Path) -> List[Dict[str, Any]]:
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

def get_date_filename(date: datetime) -> Path:
    return OUTPUT_DIR / f"{date.strftime('%m-%d-%Y')}.json"

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

def clean_html_text(html: str) -> str:
    """Remove HTML tags from text and clean up whitespace."""
    if not html:
        return ""
    # Use BeautifulSoup to remove HTML tags
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    # Clean up multiple spaces and newlines
    return ' '.join(text.split())

def crawl(config_path: str = "config.yaml", force: bool = False) -> None:
    """
    Crawl and process feed items.
    
    Args:
        config_path: Path to the configuration file
        force: If True, force replace existing items
    """
    feeds = load_config(Path(config_path))
    added = 0
    updated = 0
    processed_items = 0

    for feed in feeds:
        source = feed["name"]
        source_type = feed["type"]
        urls: List[str] = feed.get("urls", [])
        for url in urls:
            parser = get_parser(source_type)
            ctx = FeedContext(source=source, source_type=source_type)

            for item in parser.parse(url, ctx):
                guid = (item.get("guid") or item.get("link") or "").strip()
                link = (item.get("link") or "").strip()
                title = (item.get("title") or "").strip()
                summary = item.get("summary") or ""
                published = item["published"]   # aware datetime
                image = item.get("image")

                item_id = sha1(guid or link or (source + title + published.isoformat()))

                published_local = published.astimezone(TIMEZONE)
                date_path = get_date_filename(published_local)

                existing = load_day(date_path)
                if item_id in existing:
                    if not force:
                        continue
                    updated += 1
                else:
                    added += 1

                existing[item_id] = {
                    "item_id": item_id,
                    "source": source,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "guid": guid or link,
                    "image": image,
                    "published": published.isoformat(),
                }
                save_day(date_path, existing)
                processed_items += 1
                if processed_items % 10 == 0:
                    print(f"Processed {processed_items} items...")


    print(f"Crawl completed. Added {added} new items and updated {updated} items across all dates.")
    return added, updated

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Crawl and process news feeds.')
    parser.add_argument('--config', type=str, default='config.yaml',
                      help='Path to the configuration file (default: config.yaml)')
    parser.add_argument('--force', action='store_true',
                      help='Force update existing items')
    
    args = parser.parse_args()
    crawl(config_path=args.config, force=args.force)
    # Auto-build public/news/index.json and latest.json
    try:
        build_index()
    except Exception as e:
        print(f"Failed to build index: {e}")
