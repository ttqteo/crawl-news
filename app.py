import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any  # <-- use typing for 3.8
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparse
import yaml

try:
    from zoneinfo import ZoneInfo  # python >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo  # python < 3.9

OUTPUT_DIR = Path("docs/news")
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

def crawl(config_path: str = "config.yaml") -> None:
    feeds = load_config(Path(config_path))
    added = 0
    processed_items = 0

    for feed in feeds:
        source = feed["name"]
        urls: List[str] = feed.get("urls", [])
        for url in urls:
            parsed = feedparser.parse(url)
            for e in parsed.entries:
                guid = (e.get("id") or e.get("guid") or e.get("link") or "").strip()
                link = (e.get("link") or "").strip()
                title = (e.get("title") or "").strip()
                summary = clean_html_text(e.get("summary"))
                published = parse_ts(e)
                image = image_from_description(e.get("description"))

                item_id = sha1(guid or link or (source + title + published.isoformat()))
                
                # Convert published time to local timezone for grouping by date
                published_local = published.astimezone(TIMEZONE)
                date_path = get_date_filename(published_local)
                
                # Load existing items for this date
                existing = load_day(date_path)
                if item_id in existing:
                    continue
                    
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
                
                # Save this date's items
                save_day(date_path, existing)
                added += 1
                
            processed_items += 1
            if processed_items % 10 == 0:
                print(f"Processed {processed_items} items...")

    print(f"Crawl completed. Added {added} new items across all dates.")

if __name__ == "__main__":
    crawl()
