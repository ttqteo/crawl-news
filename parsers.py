# parsers.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Dict, Any, Optional, List
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparse


# ---------- local utilities (self-contained to avoid circular imports) ----------

def _clean_html_text(html: Optional[str]) -> str:
    """Remove HTML tags from text and clean up whitespace."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())

def _image_from_html(html: Optional[str]) -> Optional[str]:
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    img = soup.find("img")
    return img.get("src").strip() if (img and img.get("src")) else None

def _get_content_html(e: dict) -> Optional[str]:
    """Feedparser maps <content:encoded> to e['content'][0]['value'] if present."""
    try:
        contents = e.get("content") or []
        if contents and isinstance(contents, list):
            val = contents[0].get("value")
            return val if isinstance(val, str) and val.strip() else None
    except Exception:
        pass
    return None

def _first_media_url(e: dict) -> Optional[str]:
    """Try media:content / media:thumbnail arrays first."""
    media = e.get("media_content") or e.get("media_thumbnail") or []
    if isinstance(media, list) and media:
        url = media[0].get("url")
        return url.strip() if isinstance(url, str) else None
    return None

def _parse_ts(entry: Dict[str, Any]) -> datetime:
    """Robust timestamp parsing (UTC). Mirrors your app.py logic."""
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


# ---------- parser classes ----------

@dataclass
class FeedContext:
    source: str
    source_type: str

class BaseParser:
    def parse(self, url: str, ctx: FeedContext) -> Iterable[Dict[str, Any]]:
        raise NotImplementedError

class GenericRSSParser(BaseParser):
    """Default parser for standard RSS/Atom feeds."""
    def parse(self, url: str, ctx: FeedContext) -> Iterable[Dict[str, Any]]:
        parsed = feedparser.parse(url)
        for e in parsed.entries:
            guid = (e.get("id") or e.get("guid") or e.get("link") or "").strip()
            link = (e.get("link") or "").strip()
            title = (e.get("title") or "").strip()

            # prefer <summary> then <description>
            desc_html = e.get("summary") or e.get("description")
            summary = _clean_html_text(desc_html) if desc_html else ""

            published = _parse_ts(e)

            # image: media:* > first <img> in description
            image = _first_media_url(e)
            if not image and desc_html:
                image = _image_from_html(desc_html)

            yield {
                "guid": guid,
                "link": link,
                "title": title,
                "summary": summary,
                "published": published,   # aware datetime (UTC)
                "image": image,
                "raw": e,                 # optional for debugging
            }

class VietstockParser(GenericRSSParser):
    """
    Vietstock puts a thumbnail <img> inside <description>.
    GenericRSSParser already covers this behavior, so no extra work needed.
    """
    pass

class MarketTimesParser(BaseParser):
    """
    MarketTimes (OneCMS) usually includes <content:encoded> with full HTML
    and a plain <description> too.

    Strategy:
      - summary: prefer <description>; else textify <content:encoded>
      - image: media:* > <img> in content:encoded > <img> in description
    """
    def parse(self, url: str, ctx: FeedContext) -> Iterable[Dict[str, Any]]:
        parsed = feedparser.parse(url)
        for e in parsed.entries:
            guid = (e.get("guid") or e.get("id") or e.get("link") or "").strip()
            link = (e.get("link") or "").strip()
            title = (e.get("title") or "").strip()

            content_html = _get_content_html(e)
            desc_html = e.get("summary") or e.get("description")

            # summary
            summary = _clean_html_text(desc_html) if desc_html else _clean_html_text(content_html)

            published = _parse_ts(e)

            # image
            image = _first_media_url(e)
            if not image and content_html:
                image = _image_from_html(content_html)
            if not image and desc_html:
                image = _image_from_html(desc_html)

            yield {
                "guid": guid,
                "link": link,
                "title": title,
                "summary": summary,
                "published": published,
                "image": image,
                "raw": e,
            }


# ---------- registry & accessor ----------

PARSER_REGISTRY = {
    "rss": GenericRSSParser(),
    "vietstock": VietstockParser(),
    "markettimes": MarketTimesParser(),
}

def get_parser(source_type: str) -> BaseParser:
    """Return a parser by source_type, defaulting to 'rss'."""
    return PARSER_REGISTRY.get(source_type, PARSER_REGISTRY["rss"])
