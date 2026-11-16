#!/usr/bin/env python3
"""
Fetch Alberta (Canada) registered iGaming sites from the Alberta iGaming Corporation (AiGC).
Source: https://www.abigaming.ca/operators/registered-igaming-sites/

Each operator is a card with a heading (operator name), a "Details" link
(internal) and a "Visit site ↗" link (the operator's own site). We extract the
"Visit site" link of every card and clean it the same way as fetch_canada.py.

Output: alberta.csv  (canonical GambleEagle format)
  Line 1  : datetime stamp in Paris time — YYYYMMDD HH:MM
  Lines 2+: one clean URL per line (page order, exact duplicates removed)
"""

import os
import re
import sys
import time
import traceback
from datetime import datetime

import requests
from bs4 import BeautifulSoup

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

SOURCE_URL   = "https://www.abigaming.ca/operators/registered-igaming-sites/"
OUTPUT_FILE  = "alberta.csv"
MIN_EXPECTED = 20      # page currently lists ~50; abort rather than write a broken CSV
MAX_RETRIES  = 3
RETRY_DELAY  = 5
DEBUG_FILE   = "alberta_debug.html"

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-CA,en;q=0.9',
}

# ── Canonical CSV writer ──────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
    """
    Line 1: datetime stamp in Paris time — YYYYMMDD HH:MM
    Lines 2+: one clean URL per line, no header, no extra columns.
    """
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in urls:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(urls)} URLs → {filepath}  (stamp: {stamp})")

# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_url(href):
    """Same cleaning as fetch_canada.py, plus fragment removal (e.g. 'betty.ca#')."""
    u = href.strip()
    u = re.sub(r'^https?://', '', u, flags=re.IGNORECASE)
    u = re.sub(r'^www\.', '', u, flags=re.IGNORECASE)
    u = u.split('#', 1)[0]                      # drop fragment (bare '#' or '#/...')
    u = u.lower()
    # Ensure a slash separates the hostname from any query string
    # e.g. luckyliner.com?foo=1 → luckyliner.com/?foo=1
    u = re.sub(r'^([^/?#]+)(\?)', r'\1/\2', u)
    return u

def norm(text):
    return re.sub(r'\s+', ' ', text or '').strip()

def is_visit_link(a):
    href = (a.get('href') or '').strip()
    return href.lower().startswith('http') and 'visit site' in norm(a.get_text(' ')).lower()

def card_name(a):
    """Operator name for logging: first heading in the card containing only this link."""
    node = a
    while node.parent is not None and node.parent.name not in ('body', 'html', '[document]'):
        inside = [v for v in node.parent.find_all('a', href=True) if is_visit_link(v)]
        if len(inside) > 1:
            break
        node = node.parent
    h = node.find(['h1', 'h2', 'h3', 'h4', 'h5'])
    return norm(h.get_text(' ')) if h else ''

# ── Fetcher ───────────────────────────────────────────────────────────────────

def fetch_page():
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES}...")
            r = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return BeautifulSoup(r.content, 'html.parser'), None
        except Exception as e:
            last_err = e
            print(f"    ✗ Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    # Fallback: browser-impersonating client (in case of bot protection)
    try:
        from curl_cffi import requests as cffi_requests
        print("    ↳ Trying curl_cffi (chrome impersonation)...")
        r = cffi_requests.get(SOURCE_URL, impersonate="chrome", timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.content, 'html.parser'), None
    except Exception as e:
        print(f"    ✗ curl_cffi failed: {e}")
    return None, f"Failed to fetch page: {last_err}"

# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_sites(soup):
    visit_links = [a for a in soup.find_all('a', href=True) if is_visit_link(a)]
    print(f"  Found {len(visit_links)} 'Visit site' links")

    results, seen = [], set()
    for a in visit_links:
        href = a['href'].strip()
        cleaned = clean_url(href)
        name = card_name(a) or cleaned
        if not cleaned or '.' not in cleaned:
            print(f"  ✗ {name:<38} invalid URL: {href}")
            continue
        if cleaned in seen:
            print(f"  = {name:<38} duplicate, skipped: {cleaned}")
            continue
        seen.add(cleaned)
        results.append(cleaned)
        print(f"  ✓ {name:<38} → {cleaned}")
    return results

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("CANADA (ALBERTA) REGISTERED iGAMING SITES")
    print("=" * 60)
    print(f"🔍  Fetching: {SOURCE_URL}")

    soup, error = fetch_page()
    if error:
        print(f"❌  {error}")
        return

    urls = extract_sites(soup)

    if not urls:
        print("❌  No 'Visit site' links found — page structure may have changed.")
        with open(DEBUG_FILE, 'w', encoding='utf-8') as f:
            f.write(str(soup))
        print(f"    Page HTML saved to {DEBUG_FILE} for inspection.")
        return

    print(f"\n📊  Total unique URLs: {len(urls)}")
    if len(urls) < MIN_EXPECTED:
        print(f"❌  Only {len(urls)} URLs — below minimum of {MIN_EXPECTED}. Not writing CSV.")
        return

    write_canonical_csv(urls, OUTPUT_FILE)
    print("✅  Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\n❌  UNEXPECTED ERROR:")
        traceback.print_exc()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
