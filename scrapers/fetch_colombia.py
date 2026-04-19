#!/usr/bin/env python3
"""
Colombia Licensed Gambling Sites Scraper
Sources: 
  - Juegos Online (Column 2)
  - Novedosos (Column 5)
"""

import re
import time
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Timezone handling
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

# List of tuples: (URL, Target Column Index)
# Juegos Online -> Column 2 (Index 1)
# Novedosos -> Column 5 (Index 4)
SOURCES = [
    ("https://www.coljuegos.gov.co/publicaciones/301841/juegosonline/", 1),
    ("https://www.coljuegos.gov.co/publicaciones/300440/novedosos/", 4)
]

MIN_EXPECTED = 15
MAX_RETRIES  = 5
RETRY_DELAY  = 8 

EXCLUDED_DOMAINS = ["coljuegos.gov.co", "gov.co", "twitter.com", "facebook.com", "instagram.com", "youtube.com"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

# ── Canonical CSV writer ──────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    sorted_urls = sorted(list(set(urls)))
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in sorted_urls:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(sorted_urls)} records → {filepath}  (stamp: {stamp})")
    return sorted_urls

# ── URL cleaner ───────────────────────────────────────────────────────────────

def clean_url(raw):
    """Strip protocol, www, and trailing slashes. Preserves internal paths."""
    url = raw.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url.rstrip('/')

def is_excluded(url):
    return any(ex in url for ex in EXCLUDED_DOMAINS)

# ── Fetcher ───────────────────────────────────────────────────────────────────

def fetch_page(url):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES}...")
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return BeautifulSoup(r.content, "html.parser"), None
        except Exception as e:
            print(f"    ✗ Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return None, "Failed after max retries"

# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_urls_from_table(soup, col_index):
    urls = set()
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        
        # Ensure the row has enough columns for the target index
        if len(cells) > col_index:
            target_cell = cells[col_index]
            
            # 1. Look for <a> tags
            links = target_cell.find_all("a", href=True)
            for a in links:
                href = a["href"].strip()
                if href.startswith("http") and not is_excluded(href):
                    cleaned = clean_url(href)
                    if "." in cleaned:
                        urls.add(cleaned)
                        print(f"  Found: {cleaned}")
            
            # 2. Text fallback if no link found
            if not links:
                text = target_cell.get_text(strip=True)
                if text and "." in text and not is_excluded(text):
                    potential = text.split()[0]
                    cleaned = clean_url(potential)
                    if "." in cleaned:
                        urls.add(cleaned)
                        print(f"  Found (text): {cleaned}")

    return list(urls)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇨🇴  COLOMBIA LICENSED OPERATOR SCRAPER (COLJUEGOS)")
    print("=" * 60)

    all_raw_urls = []

    for url, col_idx in SOURCES:
        page_name = "Juegos Online" if "juegosonline" in url else "Novedosos"
        print(f"\n🔍  Scanning {page_name} (Col {col_idx + 1})...")
        
        soup, error = fetch_page(url)
        if error:
            print(f"❌  {error}")
            continue

        found = extract_urls_from_table(soup, col_idx)
        print(f"✅  Extracted {len(found)} URLs")
        all_raw_urls.extend(found)
        time.sleep(1)

    if not all_raw_urls:
        print("\n❌  No URLs found across pages.")
        return

    unique_urls = write_canonical_csv(all_raw_urls, 'colombia.csv')

    print(f"📊  Total unique records written: {len(unique_urls)}")
    print(f"\n🔍  Preview (first 15):")
    for u in unique_urls[:15]:
        print(f"    {u}")

    if len(unique_urls) < MIN_EXPECTED:
         print(f"\n⚠️  Warning: Found {len(unique_urls)} records — below minimum.")

    print("\n✅  Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
    
    print("\n" + "=" * 60)
    input("Press [RETURN] to exit...")