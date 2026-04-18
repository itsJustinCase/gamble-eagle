#!/usr/bin/env python3
"""
Pennsylvania Licensed Gambling Sites Scraper
=============================================
Source: Pennsylvania Gaming Control Board (PGCB)

Scrapes four pages:
  - Interactive Gaming:   https://gamingcontrolboard.pa.gov/interactive-gaming-operators
  - Sports Wagering:      https://gamingcontrolboard.pa.gov/online-sports-wagering-licensed-operators
  - Online Poker:         https://gamingcontrolboard.pa.gov/online-poker-operators
  - Fantasy Contests:     https://gamingcontrolboard.pa.gov/online-fantasy-contest-operators

Each page has operator cards (div.pgcb-card) with a pgcb-card-link anchor.
The href of that anchor is the licensed URL.

Output: PA.csv
  Line 1: timestamp (YYYYMMDD HH:MM Paris time)
  Lines 2+: url,category  — two columns, no header row
  Categories: igaming | sportsbetting | poker | fantasy

Requirements:
    pip install requests beautifulsoup4
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo('Europe/Paris')
    def _paris_now():
        return datetime.now(_PARIS)
except ImportError:
    import pytz
    _PARIS = pytz.timezone('Europe/Paris')
    def _paris_now():
        return datetime.now(_PARIS)

# ── Config ────────────────────────────────────────────────────────────────────

SOURCES = [
    ("igaming",       "https://gamingcontrolboard.pa.gov/interactive-gaming-operators"),
    ("sportsbetting", "https://gamingcontrolboard.pa.gov/online-sports-wagering-licensed-operators"),
    ("poker",         "https://gamingcontrolboard.pa.gov/online-poker-operators"),
    ("fantasy",       "https://gamingcontrolboard.pa.gov/online-fantasy-contest-operators"),
]

MIN_EXPECTED = 5
MAX_RETRIES  = 5
RETRY_DELAY  = 5
PAGE_DELAY   = 1

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── CSV writer — two-column format ───────────────────────────────────────────

def write_pa_csv(records, filepath):
    """
    PA-specific CSV:
      Line 1: timestamp
      Lines 2+: url,category  (no header)
    Deduplicates by (url, category) pair so a URL licensed under
    multiple categories appears once per category.
    """
    seen = set()
    unique = []
    for url, cat in records:
        key = (url.lower(), cat)
        if key not in seen:
            seen.add(key)
            unique.append((url, cat))
    unique.sort(key=lambda x: (x[0], x[1]))

    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url, cat in unique:
            f.write(f"{url},{cat}\n")
    print(f"💾  Saved {len(unique)} records → {filepath}  (stamp: {stamp})")
    return unique

# ── URL cleaner ───────────────────────────────────────────────────────────────

def clean_url(raw):
    """Strip protocol and www. Preserve paths and trailing slashes."""
    url = raw.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url

# ── Fetcher with retries ──────────────────────────────────────────────────────

def fetch_page(url):
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES}...")
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            print(f"    ✓ Loaded (HTTP {r.status_code})")
            return BeautifulSoup(r.content, "html.parser"), None
        except Exception as e:
            last_error = str(e)
            print(f"    ✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ Waiting {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
    return None, f"Failed after {MAX_RETRIES} attempts — {last_error}"

# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_from_page(soup, category):
    """
    Find all div.pgcb-card elements and extract the href from the
    pgcb-card-link anchor inside each card.
    Falls back to any anchor with an http href if class is missing.
    """
    records = []
    cards = soup.find_all("div", class_=re.compile(r'\bpgcb-card\b'))

    if not cards:
        print(f"    ⚠️  No pgcb-card divs found — check page structure.")
        return records

    print(f"    📦  Found {len(cards)} cards")

    for card in cards:
        # Primary: anchor with class pgcb-card-link
        a = card.find("a", class_="pgcb-card-link", href=True)
        # Fallback: any anchor inside the card
        if not a:
            a = card.find("a", href=True)
        if not a:
            continue

        href = a["href"].strip()
        if not href or not href.startswith("http"):
            continue

        cleaned = clean_url(href)
        if cleaned and "." in cleaned:
            records.append((cleaned, category))
            print(f"  [{category}] {cleaned}")

    return records

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇺🇸  PENNSYLVANIA LICENSED GAMBLING SITES SCRAPER (PGCB)")
    print("=" * 60)
    print(f"🔁  Retry policy: {MAX_RETRIES} attempts × {RETRY_DELAY}s delay\n")

    all_records = []

    for category, url in SOURCES:
        print(f"\n🔍  [{category.upper()}] {url}")
        soup, error = fetch_page(url)
        if error:
            print(f"    ❌  {error}")
            continue
        records = extract_from_page(soup, category)
        print(f"    ✅  {len(records)} records extracted")
        all_records.extend(records)
        time.sleep(PAGE_DELAY)

    if not all_records:
        print("\n❌  No records found across any page.")
        return

    print(f"\n📊  Total raw records: {len(all_records)}")
    unique = write_pa_csv(all_records, 'PA.csv')
    print(f"📊  Total unique records written: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"⚠️  Only {len(unique)} — below expected minimum of {MIN_EXPECTED}.")

    print(f"\n🔍  Preview (first 15):")
    for url, cat in unique[:15]:
        print(f"    {url:<55} {cat}")
    if len(unique) > 15:
        print(f"    ... and {len(unique) - 15} more")

    print("\n✅  Done.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
