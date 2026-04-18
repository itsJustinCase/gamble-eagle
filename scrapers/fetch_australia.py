#!/usr/bin/env python3
"""
Australia Licensed Gambling Sites Scraper
==========================================
Source: Australian Communications and Media Authority (ACMA)
        https://www.acma.gov.au/check-if-gambling-operator-legal

Scrapes the licensed operator table (URL column), paginated at 100 per page.
Skips entries showing "No current URL".

Pagination stop conditions (checked in order):
  1. The page returned zero URL cells (past last data page).
  2. Every URL on this page was already seen on a previous page
     (ACMA returns full page template on out-of-range requests,
      so the same nav/footer links appear — overlap detection catches this).
  3. Fewer rows than ITEMS_PER_PAGE returned — this is the last data page.

Requirements:
    pip install curl-cffi beautifulsoup4
"""

import re
import time
from bs4 import BeautifulSoup
from datetime import datetime

try:
    from curl_cffi import requests as cffi_requests
    _USE_CFFI = True
except ImportError:
    import requests as cffi_requests
    _USE_CFFI = False
    print("⚠️  curl_cffi not found — falling back to requests (may time out).")
    print("    Install with: pip install curl-cffi")

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

BASE_URL       = "https://www.acma.gov.au/check-if-gambling-operator-legal"
ITEMS_PER_PAGE = 100
MAX_RETRIES    = 5
RETRY_DELAY    = 8
PAGE_DELAY     = 2
TIMEOUT        = 60
MIN_EXPECTED   = 10
MAX_PAGES      = 20    # hard ceiling — 20 × 100 = 2000 entries, well above reality

# ── Canonical CSV writer ──────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    unique.sort()
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in unique:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(unique)} URLs → {filepath}  (stamp: {stamp})")
    return unique

# ── URL cleaner ───────────────────────────────────────────────────────────────

def clean_url(raw):
    url = raw.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url

# ── Page fetcher with retries ─────────────────────────────────────────────────

def fetch_page(page_num):
    url = f"{BASE_URL}?page={page_num}&items_per_page={ITEMS_PER_PAGE}"
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES} "
                  f"({'curl_cffi/Chrome' if _USE_CFFI else 'requests'}) — {url}")
            if _USE_CFFI:
                r = cffi_requests.get(url, impersonate="chrome120", timeout=TIMEOUT)
            else:
                r = cffi_requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            print(f"    ✓ Page {page_num} loaded (HTTP {r.status_code})")
            return BeautifulSoup(r.content, "html.parser"), None
        except Exception as e:
            last_error = str(e)
            print(f"    ✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ Waiting {RETRY_DELAY}s before retrying...")
                time.sleep(RETRY_DELAY)
    return None, f"Page {page_num} failed after {MAX_RETRIES} attempts — {last_error}"

# ── URL extractor ─────────────────────────────────────────────────────────────

def extract_urls_from_page(soup):
    """
    Returns (urls, cell_count).
    cell_count = number of URL-column cells found (including 'No current URL').
    """
    cells = soup.find_all(
        "td", headers=lambda h: h and "view-field-lwr-url-table-column" in h
    )
    if not cells:
        cells = soup.find_all(
            "td", class_=lambda c: c and "views-field-field-lwr-url" in c
        )

    urls = []
    for cell in cells:
        text = cell.get_text(strip=True)
        if not text or "no current url" in text.lower():
            continue
        a = cell.find("a", href=True)
        raw = a["href"].strip() if a else text
        if not raw or "no current url" in raw.lower():
            continue
        cleaned = clean_url(raw)
        if cleaned and "." in cleaned:
            urls.append(cleaned)

    return urls, len(cells)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇦🇺  AUSTRALIA LICENSED GAMBLING SITES SCRAPER (ACMA)")
    print("=" * 60)
    print(f"🔁  Retry policy: {MAX_RETRIES} attempts × {RETRY_DELAY}s delay")
    print(f"⏱️   Timeout: {TIMEOUT}s | 📄 Items/page: {ITEMS_PER_PAGE} | 🔢 Max pages: {MAX_PAGES}")
    if not _USE_CFFI:
        print("⚠️  curl_cffi not installed — run: pip install curl-cffi")
    print()

    all_urls   = []
    seen_urls  = set()   # tracks all URLs collected so far across pages
    failed_pages = []

    for page in range(MAX_PAGES):
        print(f"\n🔍  Processing page {page}...")
        soup, error = fetch_page(page)

        if error:
            failed_pages.append((page, error))
            print(f"⚠️   Page {page} skipped and flagged.")
            if len(failed_pages) >= 3:
                print("❌  3 consecutive failures — aborting.")
                break
            continue

        page_urls, cell_count = extract_urls_from_page(soup)

        # ── Stop condition 1: no URL-column cells at all ───────────────────
        if cell_count == 0:
            print(f"ℹ️   No URL cells on page {page} — past end of data. Stopping.")
            break

        # ── Stop condition 2: all URLs on this page already seen ───────────
        # ACMA serves a full page (with nav links etc.) even beyond last page,
        # so repeated pages would have overlapping content. If every URL we
        # extracted is one we've already collected, we've looped back.
        new_urls = [u for u in page_urls if u not in seen_urls]
        if page_urls and not new_urls:
            print(f"ℹ️   All {len(page_urls)} URLs on page {page} already seen — stopping.")
            break

        print(f"✅  Page {page}: {cell_count} cells, {len(page_urls)} URLs "
              f"({len(new_urls)} new)")
        for u in page_urls:
            print(f"    {u}")

        for u in page_urls:
            if u not in seen_urls:
                seen_urls.add(u)
                all_urls.append(u)

        # ── Stop condition 3: partial page = last data page ────────────────
        if cell_count < ITEMS_PER_PAGE:
            print(f"📄  Page {page} has {cell_count} rows (< {ITEMS_PER_PAGE}) — last page.")
            break

        time.sleep(PAGE_DELAY)

    else:
        print(f"⚠️  Reached MAX_PAGES ({MAX_PAGES}) — stopping as a safety measure.")

    if failed_pages:
        print(f"\n⚠️  {len(failed_pages)} page(s) failed:")
        for p, e in failed_pages:
            print(f"    • Page {p}: {e}")

    if not all_urls:
        print("❌  No URLs collected.")
        return

    unique = write_canonical_csv(all_urls, 'australia.csv')
    print(f"\n📊  Total unique URLs written: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"⚠️  Only {len(unique)} — below expected minimum of {MIN_EXPECTED}.")

    print(f"\n🔍  First 10 URLs:")
    for u in unique[:10]:
        print(f"    {u}")
    if len(unique) > 10:
        print(f"    ... and {len(unique) - 10} more")

    print("✅  Done.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
