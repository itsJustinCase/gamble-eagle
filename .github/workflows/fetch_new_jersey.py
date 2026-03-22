#!/usr/bin/env python3
"""
US New Jersey Licensed Gambling Sites Scraper
==============================================
Source: NJ Division of Gaming Enforcement (DGE)
        https://www.njoag.gov/about/divisions-and-offices/
        division-of-gaming-enforcement-home/sports-wagering/

Extracts URLs from plain-text <td> cells towards the end of the page.
These are bare URL strings (e.g. https://sportsbook.fanatics.com/) not
wrapped in <a> tags. Trailing slashes are preserved as-is.
Single page — no pagination needed.
"""

import re
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

SOURCE_URL  = (
    "https://www.njoag.gov/about/divisions-and-offices/"
    "division-of-gaming-enforcement-home/sports-wagering/"
)
MIN_EXPECTED = 5
MAX_RETRIES  = 5
RETRY_DELAY  = 5

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
    """
    Strip protocol and www. only.
    Trailing slash is intentionally preserved (matches source format).
    """
    url = raw.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url

def looks_like_url(text):
    """Return True if the text looks like a bare URL."""
    t = text.strip()
    return (
        t.startswith("http://") or
        t.startswith("https://") or
        re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/|$)', t)
    )

# ── Fetcher with retries ──────────────────────────────────────────────────────

def fetch_page():
    import time
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
    The DGE sports wagering page lists URLs as plain text inside <td> cells
    (no anchor wrapping). We scan every <td> whose text content looks like
    a URL and collect it.

    Also catches any <a href> links inside table cells that point off-domain,
    in case the page structure changes to use hyperlinks in a future update.
    """
    urls = []
    seen = set()

    # ── Primary: bare-text <td> cells ────────────────────────────────────────
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if looks_like_url(text):
            cleaned = clean_url(text)
            if cleaned and "." in cleaned and cleaned not in seen:
                seen.add(cleaned)
                urls.append(cleaned)
                print(f"  Found (text td): {cleaned}")

    # ── Secondary: <a href> links inside table cells (future-proofing) ────────
    if not urls:
        print("    ℹ️  No bare-URL cells found — trying anchored links in tables...")
        for td in soup.find_all("td"):
            for a in td.find_all("a", href=True):
                raw = a["href"].strip()
                if raw.startswith("http") and "njoag.gov" not in raw:
                    cleaned = clean_url(raw)
                    if cleaned and "." in cleaned and cleaned not in seen:
                        seen.add(cleaned)
                        urls.append(cleaned)
                        print(f"  Found (anchor): {cleaned}")

    return urls

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇺🇸  US NEW JERSEY LICENSED GAMBLING SITES SCRAPER (DGE)")
    print("=" * 60)
    print(f"🔁  Retry policy: {MAX_RETRIES} attempts × {RETRY_DELAY}s delay\n")

    print("🔍  Fetching DGE sports wagering page...")
    soup, error = fetch_page()

    if error:
        print(f"❌  {error}")
        return

    urls = extract_urls(soup)

    if not urls:
        print("❌  No URLs found — check the page structure.")
        return

    # Deduplicate (seen set already handles this, but sort for consistency)
    unique = sorted(set(urls))

    print(f"\n📊  Total unique URLs: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"❌  Only {len(unique)} URLs found — below minimum of {MIN_EXPECTED}.")
        print("    Aborting write to protect existing data.")
        return

    print(f"\n🔍  All URLs:")
    for u in unique:
        print(f"    {u}")

    write_canonical_csv(unique, 'NJ.csv')
    print("✅  Done.")

if __name__ == "__main__":
    main()
