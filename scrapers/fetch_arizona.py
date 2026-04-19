#!/usr/bin/env python3
"""
US Arizona Licensed Gambling Sites Scraper
Source: https://gaming.az.gov/approved-operators-retail-locations-0
"""

import re
import time
import os
from curl_cffi import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse

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

SOURCE_URL   = "https://gaming.az.gov/approved-operators-retail-locations-0"
MIN_EXPECTED = 15
MAX_RETRIES  = 5
RETRY_DELAY  = 8 

EXCLUDED_DOMAINS = ["gaming.az.gov", "az.gov"]

# Manual URLs to ensure are always included
MANUAL_URLS = [
    "fantasygolfchampionships.shgn.com",
    "nfc.shgn.com",
    "leaguesafe.com",
    "fanball.com/lobby/salary-cap"
]

# ── Canonical CSV writer ──────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    # Sort alphabetically before writing
    sorted_urls = sorted(urls)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in sorted_urls:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(sorted_urls)} URLs → {filepath}  (stamp: {stamp})")

# ── URL cleaner ───────────────────────────────────────────────────────────────

def clean_url(raw):
    """Strip protocol, www, and query parameters. Preserve paths."""
    parsed = urlparse(raw.strip())
    url = f"{parsed.netloc}{parsed.path}"
    url = re.sub(r'^www\.', '', url)
    return url.rstrip('/')

def is_excluded(url):
    return any(ex in url for ex in EXCLUDED_DOMAINS)

# ── Fetcher ───────────────────────────────────────────────────────────────────

def fetch_page():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES}...")
            r = requests.get(SOURCE_URL, impersonate="chrome", timeout=30)
            r.raise_for_status()
            return BeautifulSoup(r.content, "html.parser"), None
        except Exception as e:
            print(f"    ✗ Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ Waiting {RETRY_DELAY}s before retrying...")
                time.sleep(RETRY_DELAY)
    return None, "Failed after max retries"

# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_urls(soup):
    urls = set()
    tables = soup.find_all("table")
    for table in tables:
        for a in table.find_all("a", href=True):
            raw_href = a["href"].strip()
            if not raw_href.startswith("http") or is_excluded(raw_href):
                continue
            cleaned = clean_url(raw_href)
            if cleaned and "." in cleaned:
                urls.add(cleaned)
                print(f"  Found: {cleaned}")
    
    # Add manual URLs
    for m_url in MANUAL_URLS:
        if m_url not in urls:
            urls.add(m_url)
            print(f"  Added manual: {m_url}")
            
    return list(urls)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇺🇸  US ARIZONA LICENSED OPERATOR SCRAPER")
    print("=" * 60)
    print(f"🔁  Retry policy: {MAX_RETRIES} attempts × {RETRY_DELAY}s delay\n")

    print(f"🔍  Fetching: {SOURCE_URL}")
    soup, error = fetch_page()

    if error:
        print(f"❌  {error}")
        return

    urls = extract_urls(soup)

    if not urls:
        print("❌  No URLs found.")
        return

    print(f"\n📊  Total unique URLs: {len(urls)}")

    if len(urls) < MIN_EXPECTED:
        print(f"❌  Found {len(urls)} URLs — below minimum of {MIN_EXPECTED}. Aborting.")
        return

    write_canonical_csv(urls, 'AZ.csv')
    print("✅  Done.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")