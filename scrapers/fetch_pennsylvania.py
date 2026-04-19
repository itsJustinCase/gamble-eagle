#!/usr/bin/env python3
"""
Pennsylvania Licensed Gambling Sites Scraper
=============================================
Source: Pennsylvania Gaming Control Board (PGCB)
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

# ── CSV writer — URL Only Format ──────────────────────────────────────────────

def write_pa_csv(records, filepath):
    """
    PA-specific CSV:
      Line 1: timestamp
      Lines 2+: url (NO category)
    """
    # We use a set of URLs to ensure no duplicates, regardless of category
    unique_urls = sorted(list(set(r[0] for r in records)))

    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in unique_urls:
            f.write(f"{url}\n")
    
    print(f"💾  Saved {len(unique_urls)} unique URLs → {filepath}  (stamp: {stamp})")
    return unique_urls

# ── URL cleaner ───────────────────────────────────────────────────────────────

def clean_url(raw):
    """Strip protocol, www, and trailing slashes."""
    url = raw.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url.rstrip('/')

# ── Fetcher with retries ──────────────────────────────────────────────────────

def fetch_page(url):
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES}...")
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.content, "html.parser"), None
        except Exception as e:
            last_error = str(e)
            print(f"    ✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return None, f"Failed after {MAX_RETRIES} attempts — {last_error}"

# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_from_page(soup, category):
    records = []
    cards = soup.find_all("div", class_=re.compile(r'\bpgcb-card\b'))

    for card in cards:
        a = card.find("a", class_="pgcb-card-link", href=True)
        if not a:
            a = card.find("a", href=True)
        if not a:
            continue

        href = a["href"].strip()
        if not href or not href.startswith("http"):
            continue

        cleaned = clean_url(href)
        if cleaned and "." in cleaned:
            # We keep the category in the temporary list for the summary report
            records.append((cleaned, category))
    return records

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇺🇸  PENNSYLVANIA LICENSED GAMBLING SITES SCRAPER (PGCB)")
    print("=" * 60)

    all_records = []
    category_counts = {"igaming": 0, "sportsbetting": 0, "poker": 0, "fantasy": 0}

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

    # Calculate category totals before we flatten for the CSV
    # Note: If a URL is in multiple categories, it is counted in each category total
    for _, cat in all_records:
        if cat in category_counts:
            category_counts[cat] += 1

    # Write the clean URL list to the CSV
    unique_urls = write_pa_csv(all_records, 'PA.csv')

    print(f"📊  Total unique URLs written: {len(unique_urls)}")

    print(f"\n🔍  Preview (first 15):")
    for url in unique_urls[:15]:
        print(f"    {url}")
    if len(unique_urls) > 15:
        print(f"    ... and {len(unique_urls) - 15} more")

    # Required Category Summary (Total hits per category from source)
    print(f"\ntotal igaming: {category_counts['igaming']}")
    print(f"total sportsbetting: {category_counts['sportsbetting']}")
    print(f"total poker: {category_counts['poker']}")
    print(f"total fantasy: {category_counts['fantasy']}")

    if len(unique_urls) < MIN_EXPECTED:
         print(f"\n⚠️  Warning: Found {len(unique_urls)} records — below minimum.")

    print("\n✅  Done.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")