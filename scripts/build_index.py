#!/usr/bin/env python3
import os, json, glob, datetime


def parse_date(date_str: str):
    """Extract dates from filenames like MM-dd-YYYY.json"""
    m, d, y = map(int, date_str.split("-"))
    return datetime.date(y, m, d)


def build_index(base: str = "docs/news") -> int:
    """
    Build docs/news/index.json.

    Returns: count_of_dates
    """
    BASE = base
    os.makedirs(BASE, exist_ok=True)

    files = [
        f for f in glob.glob(os.path.join(BASE, "*.json"))
        if os.path.basename(f) not in ("index.json")
    ]

    dates: list[str] = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        try:
            parse_date(name)  # validate
            dates.append(name)
        except Exception:
            pass

    dates = sorted(set(dates), key=parse_date, reverse=True)

    # Collect digests
    digest_files = glob.glob(os.path.join(BASE, "digest-*.json"))
    digests = sorted(set(os.path.basename(f).replace("digest-", "").replace(".json", "") for f in digest_files), key=parse_date, reverse=True)

    # Write index.json
    with open(os.path.join(BASE, "index.json"), "w", encoding="utf-8") as out:
        json.dump({"dates": dates, "digests": digests}, out, ensure_ascii=False, separators=(",", ":"))

    print(f"Index built with {len(dates)} date(s) and {len(digests)} digest(s).")
    return len(dates)


if __name__ == "__main__":
    # Simple CLI run
    build_index()
