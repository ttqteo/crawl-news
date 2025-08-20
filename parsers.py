# parsers.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Dict, Any, Optional, List
from datetime import datetime, timezone
import html

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparse
import re

from datetime import datetime, timezone, timedelta  # add timedelta

BR_RE = re.compile(r'</?br\s*/?>', flags=re.I)
VN_TZ = timezone(timedelta(hours=7))

# ---------- local utilities (self-contained to avoid circular imports) ----------

def _clean_html_text(html: Optional[str]) -> str:
    """Remove HTML tags from text and clean up whitespace."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())

def _onecms_summary(html_in: str) -> str:
    if not html_in:
        return ""
    s = html.unescape(html_in)
    s = BR_RE.sub('\n', s)
    # take after the first break
    tail = s.split('\n', 1)[-1] if '\n' in s else s
    return _clean_html_text(tail)

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

def _to_utc_assume_vn(dt: datetime) -> datetime:
    """Return UTC datetime; if naive, assume Asia/Ho_Chi_Minh (+07:00)."""
    if not isinstance(dt, datetime):
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=VN_TZ)
    return dt.astimezone(timezone.utc)

def _parse_ts(entry: Dict[str, Any]) -> datetime:
    for key in ("published", "pubDate", "updated"):
        v = entry.get(key)
        if v:
            try:
                dt = dtparse.parse(v)
                return _to_utc_assume_vn(dt)   # << use helper
            except Exception:
                pass
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                dt = datetime(*st[:6])
                return _to_utc_assume_vn(dt)   # << use helper
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

class NguoiQuanSatParser(BaseParser):
    """
    NguoiQuanSat (OneCMS-like) places an <img> inside <description> and also
    includes full HTML in <content:encoded>.

    Strategy:
      - summary: prefer textified <description>; else textify <content:encoded>
                 then trim to a concise blurb.
      - image: media:* > <img> in description > <img> in content:encoded
    """
    def parse(self, url: str, ctx: FeedContext) -> Iterable[Dict[str, Any]]:
        parsed = feedparser.parse(url, sanitize_html=False, resolve_relative_uris=False)
        for e in parsed.entries:
            guid = (e.get("guid") or e.get("id") or e.get("link") or "").strip()
            link = (e.get("link") or "").strip()
            title = (e.get("title") or "").strip()

            content_html = _get_content_html(e)
            desc_html = e.get("summary") or e.get("description")

            summary_src = desc_html or content_html
            summary_text = _onecms_summary(summary_src)  # or _clean_html_text(summary_src)
            if len(summary_text) > 300:
                summary_text = summary_text[:297].rstrip() + "..."
            summary_text = summary_text.replace("]]>", "")
            
            published = _parse_ts(e)

            # image
            image = _first_media_url(e)
            if not image and desc_html:
                image = _image_from_html(desc_html)
            if not image and content_html:
                image = _image_from_html(content_html)

            yield {
                "guid": guid,
                "link": link,
                "title": title,
                "summary": summary_text,
                "published": published,
                "image": image,
                "raw": e,
            }

class VnExpressParser(BaseParser):
    """
    VnExpress (OneCMS-like) places an <img> inside <description> and also
    includes full HTML in <content:encoded>.

    Strategy:
      - summary: prefer textified <description>; else textify <content:encoded>
                 then trim to a concise blurb.
      - image: media:* > <img> in description > <img> in content:encoded
    """
    def parse(self, url: str, ctx: FeedContext) -> Iterable[Dict[str, Any]]:
        parsed = feedparser.parse(url, sanitize_html=False, resolve_relative_uris=False)
        for e in parsed.entries:
            guid = (e.get("guid") or e.get("id") or e.get("link") or "").strip()
            link = (e.get("link") or "").strip()
            title = (e.get("title") or "").strip()

            content_html = _get_content_html(e)
            desc_html = e.get("summary") or e.get("description")

            summary_src = desc_html or content_html
            summary_text = _onecms_summary(summary_src)  # or _clean_html_text(summary_src)
            if len(summary_text) > 300:
                summary_text = summary_text[:297].rstrip() + "..."
            summary_text = summary_text.replace("]]>", "")
            
            published = _parse_ts(e)

            # image
            image = _first_media_url(e)
            if not image and desc_html:
                image = _image_from_html(desc_html)
            if not image and content_html:
                image = _image_from_html(content_html)

            yield {
                "guid": guid,
                "link": link,
                "title": title,
                "summary": summary_text,
                "published": published,
                "image": image,
                "raw": e,
            }

import requests
from urllib.parse import urljoin

class TinNhanhChungKhoanHTMLParser(BaseParser):
    """
    Crawl listing pages on tinnhanhchungkhoan.vn, then open each article page.
    Extract: guid/link/title/summary/image/published (UTC aware).
    """
    ARTICLE_RE = re.compile(
        r"^https?://(?:www\.|m\.)?tinnhanhchungkhoan\.vn/.+-post\d+\.html$",
        re.IGNORECASE,
    )

    def _fetch(self, url: str, timeout: int = 15) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; tnck-crawler/1.0)"
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.text

    def _resolve_article_urls(self, list_html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(list_html, "lxml")
        links = set()

        # 🔑 restrict to <div class="main-column">
        main_col = soup.select_one("div.main-column")
        if not main_col:
            return []

        for a in main_col.select("a[href]"):
            href = urljoin(base_url, a["href"])
            if self.ARTICLE_RE.match(href):
                links.add(href.split("#")[0])

        return sorted(links)


    def _first_paragraph(self, soup: BeautifulSoup) -> str:
        # Try common article body containers; fall back to meta description
        containers = [
            "div.detail-content", "div.content-detail", "div.article__content",
            "div.main-article", "div#contentdetail", "article"
        ]
        for sel in containers:
            node = soup.select_one(sel)
            if not node:
                continue
            p = node.find("p")
            if p:
                return _clean_html_text(str(p))
        md = soup.find("meta", attrs={"name": "description"})
        return (md.get("content", "").strip() if md else "") or ""

    def _parse_published(self, soup: BeautifulSoup) -> datetime:
        # Prefer meta timestamps
        for prop in ("article:published_time", "og:updated_time", "pubdate"):
            m = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
            if m and m.get("content"):
                try:
                    return dtparse.parse(m["content"]).astimezone(timezone.utc)
                except Exception:
                    pass
        # Fallback visible time like 30/07/2025 15:46
        tnode = soup.find(["time", "span", "div"], string=re.compile(r"\d{1,2}/\d{1,2}/\d{4}"))
        if tnode:
            try:
                return dtparse.parse(tnode.get_text(" ", strip=True), dayfirst=True).astimezone(timezone.utc)
            except Exception:
                pass
            
        return datetime.now(timezone.utc)

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            return og["content"].strip()
        img = soup.select_one("div.detail-content img, article img, div.main-article img")
        return (img.get("src").strip() if img and img.get("src") else None)

    def parse(self, url: str, ctx: FeedContext) -> Iterable[Dict[str, Any]]:
        try:
            listing_html = self._fetch(url)
        except Exception as e:
            print(f"[TNCK] list fetch failed: {url} -> {e}")
            return []

        article_urls = self._resolve_article_urls(listing_html, url)
        for link in article_urls:
            try:
                html = self._fetch(link)
                soup = BeautifulSoup(html, "lxml")

                # title
                title = (
                    (soup.find("meta", attrs={"property": "og:title"}) or {}).get("content")
                    or (soup.find("h1") or {}).get_text(strip=True)
                    or ""
                ).strip()

                # summary, image, time
                summary = self._first_paragraph(soup)
                image = self._extract_image(soup)
                published = self._parse_published(soup)

                yield {
                    "guid": link,
                    "link": link,
                    "title": title,
                    "summary": summary,
                    "published": published,   # aware datetime (UTC)
                    "image": image,
                }
            except Exception as e:
                print(f"[TNCK] skip {link}: {e}")
                continue

class VnEconomyHTMLParser(BaseParser):
    """
    Crawl listing pages on vneconomy.vn (e.g. /chung-khoan.htm), then open each
    article page and extract title/summary/image/published (UTC).
    """

    # Accept normal and www. subdomain; accept any .htm article (exclude obvious hubs)
    ARTICLE_RE = re.compile(
        r"^https?://(?:www\.)?vneconomy\.vn/(?!chu-de/|tag/|video/|photo/)[^?#]+\.htm$",
        re.IGNORECASE,
    )

    def _fetch(self, url: str, timeout: int = 15) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; vneco-crawler/1.0)",
            "Accept-Language": "vi,en;q=0.8",
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.text

    def _normalize_href(self, href: str) -> str:
        # strip query/hash + any whitespace/zero-width
        href = href.split("?", 1)[0].split("#", 1)[0]
        return "".join(href.split())

    def _resolve_article_urls(self, list_html: str, base_url: str) -> List[str]:
        soup = BeautifulSoup(list_html, "lxml")
        links: set[str] = set()

        # Exclude anything inside the top nav
        header_nav = soup.select_one(".layout-header-menu-main")

        # 🔒 Only crawl featured cards
        # If the page sometimes uses just one of these classes, include fallbacks:
        card_selectors = [
            ".featured-row_item.featured-column_item",
            ".featured-column_item",
            ".featured-row_item",
        ]

        cards = []
        for sel in card_selectors:
            cards.extend(soup.select(sel))

        # De-dup card nodes while preserving order
        seen_ids = set()
        uniq_cards = []
        for c in cards:
            if id(c) in seen_ids: continue
            uniq_cards.append(c); seen_ids.add(id(c))

        # Known unwanted menu labels
        skip_titles = {
            "Thị trường - VnEconomy",
            "Multimedia - VnEconomy",
        }

        for card in uniq_cards:
            # Prefer the first anchor in each card as the main article link
            a = card.find("a", href=True)
            if not a:
                continue

            # Skip if the anchor is in the header menu area
            if header_nav and a.find_parent(class_="layout-header-menu-main"):
                continue

            # Skip by text guard (backup)
            t = (a.get_text(" ", strip=True) or "")
            if t in skip_titles or t.endswith(" - VnEconomy"):
                continue

            href = urljoin(base_url, a["href"])
            norm = self._normalize_href(href)

            # Keep only real article pages
            if self.ARTICLE_RE.search(norm):
                links.add(norm)

        return sorted(links)

    def _first_paragraph(self, soup: BeautifulSoup) -> str:
        # Try common article content containers
        body_selectors = [
            "article", "div.article__content", "div.detail-content",
            "div.content-detail", "div.detail__content", "div#contentdetail"
        ]
        for sel in body_selectors:
            node = soup.select_one(sel)
            if not node:
                continue
            p = node.find("p")
            if p:
                return _clean_html_text(str(p))
        # Fallback to meta description
        md = soup.find("meta", attrs={"name": "description"})
        return (md.get("content", "").strip() if md else "") or ""

    def _parse_published(self, soup: BeautifulSoup) -> datetime:
        SHIFT = timedelta(hours=7)

        def minus7_utc(dt: datetime) -> datetime:
            # ensure aware → UTC, then subtract 7h
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)  # treat naive as UTC before shifting
            dt = dt.astimezone(timezone.utc)
            return dt - SHIFT  # final is still tz-aware (UTC)

        # Prefer meta timestamps
        for prop in ("article:published_time", "og:updated_time", "pubdate"):
            m = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
            if m and m.get("content"):
                try:
                    dt = dtparse.parse(m["content"])
                    return minus7_utc(dt)
                except Exception:
                    pass

        # <time datetime="...">
        t = soup.find("time", attrs={"datetime": True})
        if t and t.get("datetime"):
            try:
                dt = dtparse.parse(t["datetime"])
                return minus7_utc(dt)
            except Exception:
                pass

        # Fallback visible time like 30/07/2025 15:46
        tnode = soup.find(["time", "span", "div"], string=re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"))
        if tnode:
            try:
                dt = dtparse.parse(tnode.get_text(" ", strip=True), dayfirst=True)
                return minus7_utc(dt)
            except Exception:
                pass

        return datetime.now(timezone.utc)

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            return og["content"].strip()
        img = soup.select_one("article img, div.detail-content img, div.detail__content img")
        return (img.get("src").strip() if img and img.get("src") else None)

    def parse(self, url: str, ctx: FeedContext) -> Iterable[Dict[str, Any]]:
        try:
            listing_html = self._fetch(url)
        except Exception as e:
            print(f"[VNECO] list fetch failed: {url} -> {e}")
            return []

        article_urls = self._resolve_article_urls(listing_html, url)

        for link in article_urls:
            try:
                html = self._fetch(link)
                soup = BeautifulSoup(html, "lxml")

                title = (
                    (soup.find("meta", attrs={"property": "og:title"}) or {}).get("content")
                    or (soup.find("h1") or {}).get_text(strip=True)
                    or ""
                ).strip()

                summary = self._first_paragraph(soup)
                image = self._extract_image(soup)
                published = self._parse_published(soup)

                yield {
                    "guid": link,
                    "link": link,
                    "title": title,
                    "summary": summary,
                    "published": published,  # aware datetime (UTC)
                    "image": image,
                }
            except Exception as e:
                print(f"[VNECO] skip {link}: {e}")
                continue

# ---------- registry & accessor ----------

PARSER_REGISTRY = {
    "rss": GenericRSSParser(),
    "vietstock": VietstockParser(),
    "markettimes": MarketTimesParser(),
    "nguoiquansat": NguoiQuanSatParser(),
    "vnexpress": VnExpressParser(),
    "tnck": TinNhanhChungKhoanHTMLParser(),
    "vneconomy": VnEconomyHTMLParser(),
}

def get_parser(source_type: str) -> BaseParser:
    """Return a parser by source_type, defaulting to 'rss'."""
    return PARSER_REGISTRY.get(source_type, PARSER_REGISTRY["rss"])
