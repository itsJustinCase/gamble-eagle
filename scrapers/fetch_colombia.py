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
import sys
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

SOURCES = [
    ("https://www.coljuegos.gov.co/publicaciones/301841/juegosonline/", 2, "Juegos Online"),
    ("https://www.coljuegos.gov.co/publicaciones/300440/novedosos/",    4, "Novedosos"),
]

MIN_EXPECTED = 15
MAX_RETRIES  = 5
RETRY_DELAY  = 8

EXCLUDED_DOMAINS = [
    "coljuegos.gov.co", "gov.co", "twitter.com", "facebook.com",
    "instagram.com", "youtube.com", "tiktok.com", "bit.ly",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Referer": "https://www.coljuegos.gov.co/",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    sorted_urls = sorted(set(urls))
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in sorted_urls:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(sorted_urls)} records → {filepath}  (stamp: {stamp})")
    return sorted_urls

def clean_url(raw):
    url = raw.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url.rstrip('/')

def is_excluded(url):
    return any(ex in url for ex in EXCLUDED_DOMAINS)

# ── Fetcher ───────────────────────────────────────────────────────────────────

def fetch_page(url):
    """Fetch with retries. Returns (soup, None) or (None, error_str)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES}...")
            r = requests.get(url, headers=HEADERS, timeout=30)

            # Detect geo-block explicitly
            if r.status_code == 403 and "allowlist" in r.text.lower():
                return None, "GEO_BLOCKED"

            r.raise_for_status()
            return BeautifulSoup(r.content, "html.parser"), None

        except Exception as e:
            print(f"    ✗ Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)

    return None, f"Failed after {MAX_RETRIES} attempts"

# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_urls_from_table(soup, col_index):
    urls = set()
    table = soup.find("table")
    if not table:
        print("    ⚠️  No <table> found on page")
        return []

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) <= col_index:
            continue

        target_cell = cells[col_index]

        # Look for <a href="http..."> links
        links = target_cell.find_all("a", href=True)
        for a in links:
            href = a["href"].strip()
            if href.startswith("http") and not is_excluded(href):
                cleaned = clean_url(href)
                if "." in cleaned:
                    urls.add(cleaned)
                    print(f"  Found: {cleaned}")

        # Text fallback if no links found in cell
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

    all_urls       = []
    geo_blocked    = []
    failed_sources = []

    for url, col_idx, name in SOURCES:
        print(f"\n🔍  Scanning {name} (Col {col_idx + 1})...")
        soup, error = fetch_page(url)

        if error == "GEO_BLOCKED":
            print(f"🌍  {name}: geo-blocked (403 - Host not in allowlist)")
            print(f"    This is an intermittent issue based on GitHub's runner IP.")
            print(f"    Re-running the workflow usually resolves it.")
            geo_blocked.append(name)
            continue
        elif error:
            print(f"❌  {name}: {error}")
            failed_sources.append((name, error))
            continue

        found = extract_urls_from_table(soup, col_idx)
        print(f"✅  Extracted {len(found)} URLs from {name}")
        all_urls.extend(found)
        time.sleep(1)

    # ── Results ───────────────────────────────────────────────────────────────

    if geo_blocked:
        print(f"\n⚠️  {'=' * 50}")
        print(f"⚠️  GEO-BLOCKED sources ({len(geo_blocked)}): {', '.join(geo_blocked)}")
        print(f"⚠️  Re-run the workflow to get a different GitHub runner IP.")
        print(f"⚠️  {'=' * 50}")

    if failed_sources:
        print(f"\n❌  Failed sources:")
        for name, err in failed_sources:
            print(f"     • {name}: {err}")

    if not all_urls:
        print("\n❌  No URLs collected — CSV not written.")
        sys.exit(1)

    unique_urls = write_canonical_csv(all_urls, 'colombia.csv')
    print(f"📊  Total unique records written: {len(unique_urls)}")

    print(f"\n🔍  Preview (first 15):")
    for u in unique_urls[:15]:
        print(f"    {u}")

    if len(unique_urls) < MIN_EXPECTED:
        print(f"\n⚠️  Warning: Found {len(unique_urls)} records — below minimum of {MIN_EXPECTED}.")

    print("\n✅  Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        raise

    print("\n" + "=" * 60)
    if not os.environ.get("CI"):
        input("Press [RETURN] to exit...")
