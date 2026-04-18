#!/usr/bin/env python3
"""
US Arizona Licensed Gambling Sites Scraper
===========================================
Source: Arizona Department of Gaming (ADG)
        https://gaming.az.gov/checkyourbet

The CheckYourBet page lists authorised sports betting operators and their URLs.
Extracts all off-site links from operator entries, stripping protocol and www.
Preserves paths (e.g. az.betmgm.com/en/sports).
Single page — no pagination needed.
Retries up to MAX_RETRIES times on failure.
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

SOURCE_URL   = "https://gaming.az.gov/checkyourbet"
MIN_EXPECTED = 5
MAX_RETRIES  = 5
RETRY_DELAY  = 5

# Domains to exclude — the regulator site itself and common nav/footer links
EXCLUDED_DOMAINS = [
    "gaming.az.gov",
    "az.gov",
    "problemgambling.az.gov",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Canonical CSV writer ──────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in urls:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(urls)} URLs → {filepath}  (stamp: {stamp})")

# ── URL cleaner ───────────────────────────────────────────────────────────────

def clean_url(raw):
    """Strip protocol and www. Preserve paths and trailing slashes."""
    url = raw.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url

def is_excluded(url):
    return any(ex in url for ex in EXCLUDED_DOMAINS)

# ── Fetcher with retries ──────────────────────────────────────────────────────

def fetch_page():
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES}...")
            r = requests.get(SOURCE_URL, headers=HEADERS, timeout=20)
            r.raise_for_status()
            print(f"    ✓ Page loaded successfully")
            return BeautifulSoup(r.content, "html.parser"), None
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            print(f"    ✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ Waiting {RETRY_DELAY}s before retrying...")
                time.sleep(RETRY_DELAY)
    return None, f"Failed after {MAX_RETRIES} attempts — last error: {last_error}"

# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_urls(soup):
    """
    The ADG CheckYourBet page lists operators with linked URLs.
    We collect all external <a href> links, excluding the regulator's own domain
    and other administrative links.

    Also catches plain-text URLs in table cells (same pattern as NJ),
    as a fallback in case the page uses bare text rather than anchors.
    """
    urls = []
    seen = set()

    # ── Primary: <a href> external links across the whole page ───────────────
    for a in soup.find_all("a", href=True):
        raw = a["href"].strip()
        if not raw.startswith("http"):
            continue
        if is_excluded(raw):
            continue
        cleaned = clean_url(raw)
        if not cleaned or "." not in cleaned:
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
            print(f"  Found (anchor): {cleaned}")

    # ── Fallback: bare-text <td> cells ───────────────────────────────────────
    if not urls:
        print("    ℹ️  No external anchor links found — trying bare-text table cells...")
        url_pattern = re.compile(
            r'^(https?://)?[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/\S*)?$'
        )
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if url_pattern.match(text) and not is_excluded(text):
                cleaned = clean_url(text)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    urls.append(cleaned)
                    print(f"  Found (text td): {cleaned}")

    return urls

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇺🇸  US ARIZONA LICENSED GAMBLING SITES SCRAPER (ADG)")
    print("=" * 60)
    print(f"🔁  Retry policy: {MAX_RETRIES} attempts × {RETRY_DELAY}s delay\n")

    print("🔍  Fetching ADG CheckYourBet page...")
    soup, error = fetch_page()

    if error:
        print(f"❌  {error}")
        return

    urls = extract_urls(soup)

    if not urls:
        print("❌  No URLs found — check the page structure.")
        return

    unique = sorted(set(urls))

    print(f"\n📊  Total unique URLs: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"❌  Only {len(unique)} URLs found — below minimum of {MIN_EXPECTED}.")
        print("    Aborting write to protect existing data.")
        return

    print(f"\n🔍  All URLs:")
    for u in unique:
        print(f"    {u}")

    write_canonical_csv(unique, 'AZ.csv')
    print("✅  Done.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
