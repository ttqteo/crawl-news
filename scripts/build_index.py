#!/usr/bin/env python3
import os, json, glob, datetime

BASE = "docs/news"
os.makedirs(BASE, exist_ok=True)

files = [
    f for f in glob.glob(os.path.join(BASE, "*.json"))
    if os.path.basename(f) not in ("index.json", "latest.json")
]

# Extract dates from filenames like MM-dd-YYYY.json
def parse_date(date_str: str):
    m, d, y = map(int, date_str.split("-"))
    return datetime.date(y, m, d)

dates = []
for f in files:
    name = os.path.splitext(os.path.basename(f))[0]
    try:
        parse_date(name)  # validate
        dates.append(name)
    except Exception:
        pass

dates = sorted(set(dates), key=parse_date, reverse=True)

# Write index.json
with open(os.path.join(BASE, "index.json"), "w", encoding="utf-8") as out:
    json.dump({"dates": dates}, out, ensure_ascii=False, separators=(",", ":"))

# Write latest.json
if dates:
    latest = dates[0]
    with open(os.path.join(BASE, f"{latest}.json"), "r", encoding="utf-8") as f:
        data = json.load(f)

    items = list(data.values())
    items.sort(key=lambda x: x.get("published", ""), reverse=True)

    payload = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "date": latest,
        "items": items
    }
    with open(os.path.join(BASE, "latest.json"), "w", encoding="utf-8") as out:
        json.dump(payload, out, ensure_ascii=False, separators=(",", ":"))

print(f"Index built with {len(dates)} date(s). Latest = {dates[0] if dates else 'N/A'}")
