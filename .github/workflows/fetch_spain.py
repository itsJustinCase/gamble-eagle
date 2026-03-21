#!/usr/bin/env python3
"""
Fetch Spain Gambling Sites from DGOJ
Extracts ALL domains with robust retry logic and failed-page reporting.

- Retries each page up to 5 times with a 5s delay between attempts
- If a page fails all retries it is skipped but flagged in the final summary
- Failed pages are listed clearly at the end and noted in the CSV
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import urllib3
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def write_canonical_csv(urls, filepath, failed_pages=None):
    """
    Write the canonical GambleEagle CSV format:
      Line 1: datetime stamp in Paris time — YYYYMMDD HH:MM
      Lines 2+: one clean URL per line, no header, no extra columns.
    If failed_pages is provided, a warning block is appended as
    commented lines (prefixed with #) so the extension ignores them
    but the information is not silently lost.
    """
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in urls:
            f.write(url.strip() + '\n')
        if failed_pages:
            f.write('# WARNING: the following pages failed and may be incomplete\n')
            for page_num, err in failed_pages:
                f.write(f'# FAILED page {page_num}: {err}\n')
    print(f"💾  Saved {len(urls)} URLs → {filepath}  (stamp: {stamp})")
    if failed_pages:
        print(f"⚠️   {len(failed_pages)} failed page(s) noted as comments in the file")

BASE_URL    = "https://www.ordenacionjuego.es/operadores-juego/operadores-licencia/operadores"
MAX_RETRIES = 5
RETRY_DELAY = 5   # seconds between retries
PAGE_DELAY  = 1   # seconds between successful pages

# ── Page fetcher with retries ─────────────────────────────────────────────────

def fetch_page(page: int) -> tuple:
    """
    Fetch a single page, retrying up to MAX_RETRIES times.
    Returns (soup, None) on success or (None, error_message) on total failure.
    """
    url = f"{BASE_URL}?page={page}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES} for page {page}...")
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            print(f"    ✓ Page {page} loaded successfully")
            return soup, None

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            print(f"    ✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ Waiting {RETRY_DELAY}s before retrying...")
                time.sleep(RETRY_DELAY)

    # All retries exhausted
    msg = f"Page {page} failed after {MAX_RETRIES} attempts — last error: {last_error}"
    print(f"    💥 {msg}")
    return None, msg

# ── Pagination helper ─────────────────────────────────────────────────────────

def has_next_page(soup, current_page: int) -> bool:
    for link in soup.find_all("a", href=True):
        m = re.search(r"page=(\d+)", link["href"])
        if m and int(m.group(1)) > current_page:
            return True
    for text in ["siguiente", "next", ">", "»"]:
        if soup.find("a", string=re.compile(text, re.IGNORECASE)):
            return True
    if not soup.find_all("div", class_="item-list"):
        return False
    if soup.find("li", class_=["pager-current", "is-active"]):
        return True
    return True

# ── Domain extraction ─────────────────────────────────────────────────────────

def extract_domains_from_item_lists(soup) -> set:
    domains = set()
    for item_list in soup.find_all("div", class_="item-list"):
        for link in item_list.find_all("a", href=True):
            domain = extract_domain_from_url(link["href"])
            if domain and is_valid_gambling_domain(domain):
                domains.add(domain)
    return domains

def extract_domain_from_url(url: str) -> str:
    domain = re.sub(r"^https?://(www\.)?", "", url)
    domain = re.sub(r"/.*$", "", domain)
    return domain.lower().strip()

def is_valid_gambling_domain(domain: str) -> bool:
    if "." not in domain or len(domain) < 4:
        return False
    if not domain.endswith((".es", ".com")):
        return False
    excluded = [
        "ordenacionjuego", "example", "test",
        "google", "facebook", "twitter", "linkedin", "youtube", "wikipedia",
    ]
    return not any(ex in domain for ex in excluded)

# ── Main extraction loop ──────────────────────────────────────────────────────

def extract_spanish_sites_all() -> tuple:
    """
    Returns (sorted_domains, failed_pages_list)
    """
    all_domains:   set  = set()
    failed_pages:  list = []   # list of (page_number, error_message)
    page = 0

    while True:
        print(f"\n🔍 Processing page {page}...")
        soup, error = fetch_page(page)

        if error:
            # Page permanently failed — record it and move on
            failed_pages.append((page, error))
            print(f"⚠️  Page {page} skipped and flagged.")
            page += 1
            continue

        page_domains = extract_domains_from_item_lists(soup)
        if page_domains:
            print(f"✅ Found {len(page_domains)} domains on page {page}")
            all_domains.update(page_domains)
        else:
            print(f"ℹ️  No domains on page {page}")

        if not has_next_page(soup, page):
            print(f"\n📄 No more pages after page {page}")
            break

        page += 1
        time.sleep(PAGE_DELAY)

    return sorted(all_domains), failed_pages

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇪🇸  SPAIN GAMBLING SITES SCRAPER")
    print("=" * 60)
    print(f"🔁  Retry policy: {MAX_RETRIES} attempts × {RETRY_DELAY}s delay\n")

    domains, failed_pages = extract_spanish_sites_all()

    if not domains and not failed_pages:
        print("❌  No domains found and no errors — check the site structure.")
        return

    # Print results
    print(f"\n🎯  Found {len(domains)} Spanish gambling domains:")
    print("=" * 50)
    for i, d in enumerate(domains, 1):
        print(f"  {i:3d}. {d}")

    # Print failed pages warning
    if failed_pages:
        print(f"\n⚠️  {'=' * 50}")
        print(f"⚠️  WARNING: {len(failed_pages)} page(s) failed after {MAX_RETRIES} retries:")
        for page_num, err in failed_pages:
            print(f"     • Page {page_num}: {err}")
        print(f"⚠️  These pages are noted as comments in the CSV — please retry manually.")
        print(f"⚠️  {'=' * 50}")
    else:
        print("\n✅  All pages loaded successfully — no failures.")

    write_canonical_csv(domains, 'spain.csv', failed_pages=failed_pages if failed_pages else None)
    print(f"📊  Total domains: {len(domains)}")
    if failed_pages:
        print(f"🚨  Failed pages: {[p for p, _ in failed_pages]}")

if __name__ == "__main__":
    main()
