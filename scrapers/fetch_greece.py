#!/usr/bin/env python3
"""
Greece Licensed Gambling Sites Scraper
========================================
Source: Hellenic Gaming Commission (HGC)
        https://certifications.gamingcommission.gov.gr/publicRecordsOnline/
        Lists/KatoxoiAdeias/AllItems.aspx

Uses the raw SharePoint list AllItems view.
Playwright is required — the list is JS-rendered.

Pagination:
  The next-page button:
    <td id="pagingWPQ2next">
      <a onclick='RefreshPageTo(event, "?Paged=TRUE&p_ID=60&PageFirstRow=31&View=...")'>
  After BS4 parses the HTML entities, onclick contains literal " and &,
  so the regex extracts the query string cleanly.
  We wait for the pagination container (#bottomPagingCellWPQ2) to be present
  before reading page.content() — this ensures the pager is rendered.

Requirements:
    pip install playwright beautifulsoup4
    playwright install chromium
"""

import re
import time
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

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

BASE_URL     = (
    "https://certifications.gamingcommission.gov.gr/publicRecordsOnline/"
    "Lists/KatoxoiAdeias/AllItems.aspx"
)
MIN_EXPECTED = 5
MAX_PAGES    = 50
PAGE_WAIT_MS = 3000    # extra settle time after rows appear

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
    url = raw.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip('/')
    return url

def looks_like_domain(text):
    t = text.strip()
    return (
        bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/\S*)?$', t))
        and ' ' not in t
        and len(t) < 100
        and 'gamingcommission' not in t.lower()
        and 'spcommon' not in t.lower()
        and 'sharepoint' not in t.lower()
        and 'microsoft' not in t.lower()
    )

# ── Page parser ───────────────────────────────────────────────────────────────

def parse_domains(html):
    """
    SharePoint renders the entire table — headers and all data rows —
    as a single flat list of <td> cells inside one <tr>.
    We therefore ignore row/column structure entirely and scan every
    <td> cell in the whole table for domain-like text.

    Some cells contain multiple semicolon-separated domains
    (e.g. 'pokerstars.gr;pokerstarscasino.gr') — we split on semicolons.
    """
    soup = BeautifulSoup(html, "html.parser")
    domains = []

    tables = soup.find_all("table")
    if not tables:
        print("    ⚠️  No tables found in HTML")
        return domains

    # Pick the table with the most cells
    data_table = max(tables, key=lambda t: len(t.find_all("td")), default=None)
    if not data_table:
        return domains

    cells = data_table.find_all("td")
    print(f"    🔎  Scanning {len(cells)} cells for domains")

    for cell in cells:
        # Always use full cell text rather than the first anchor's text.
        # Multiple domains in one cell are each a separate <a> tag
        # (e.g. www2.pamestoixima.gr; casino.pamestoixima.gr), so find("a")
        # only returns the first one. cell.get_text() captures all of them
        # joined by the semicolons that sit between the anchor tags.
        text = cell.get_text(strip=True)
        if not text:
            continue
        for part in text.split(';'):
            part = part.strip()
            if part and looks_like_domain(part):
                domains.append(clean_url(part))

    return domains

# ── Next-page URL extractor ───────────────────────────────────────────────────

def get_next_page_url(html):
    """
    Parse the pagination cell and extract the next-page query string.
    BS4 decodes HTML entities so onclick contains literal " and &.
    The regex matches that decoded form.
    Returns None on the last page.
    """
    soup = BeautifulSoup(html, "html.parser")

    # id="pagingWPQ2next" or similar — matches any WPQ variant
    next_td = soup.find("td", id=re.compile(r'paging.*next', re.IGNORECASE))
    if not next_td:
        return None

    a = next_td.find("a")
    if not a:
        return None

    onclick = a.get("onclick", "")
    # After BS4 entity decoding: RefreshPageTo(event, "?Paged=TRUE&p_ID=60&PageFirstRow=31&View=...")
    m = re.search(r'RefreshPageTo\s*\(\s*event\s*,\s*"([^"]+)"', onclick)
    if not m:
        return None

    qs = m.group(1)   # ?Paged=TRUE&p_ID=60&PageFirstRow=31&View=...
    return BASE_URL + qs

# ── Scraper ───────────────────────────────────────────────────────────────────

def scrape():
    all_domains = []
    seen = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="el-GR",
        )

        current_url = BASE_URL

        for page_num in range(1, MAX_PAGES + 1):
            print(f"\n📄  Page {page_num} — {current_url}")

            try:
                page.goto(current_url, wait_until="networkidle", timeout=60_000)
            except Exception as e:
                print(f"    ⚠️  networkidle timeout — continuing ({e})")

            # ── Wait for table rows ────────────────────────────────────────
            try:
                page.wait_for_selector("td.ms-vb2", timeout=20_000)
                print("    ✓ Table rows detected")
            except PlaywrightTimeoutError:
                print(f"    ❌  No table rows on page {page_num} — stopping.")
                break

            # ── Wait for pagination to render ──────────────────────────────
            try:
                page.wait_for_selector(
                    "td[id*='bottomPagingCell'], td[id*='paging']",
                    timeout=5_000
                )
                print("    ✓ Pagination element detected")
            except PlaywrightTimeoutError:
                print("    ℹ️  No pagination element — likely single or last page")

            # Extra settle time for any remaining JS
            page.wait_for_timeout(PAGE_WAIT_MS)

            html = page.content()

            # ── Parse domains ──────────────────────────────────────────────
            page_domains = parse_domains(html)

            if not page_domains:
                print(f"    ℹ️  No domains found on page {page_num} — stopping.")
                break

            new_count = 0
            for d in page_domains:
                if d and d not in seen:
                    seen.add(d)
                    all_domains.append(d)
                    new_count += 1
                    print(f"  Found: {d}")

            print(f"    ✅  {len(page_domains)} domains ({new_count} new)")

            # ── Get next page URL ──────────────────────────────────────────
            next_url = get_next_page_url(html)
            if not next_url:
                print(f"    📄  No next page button — done.")
                break

            print(f"    ➡️  Next page: {next_url}")
            current_url = next_url

        browser.close()

    return all_domains

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇬🇷  GREECE LICENSED GAMBLING SITES SCRAPER (HGC)")
    print("=" * 60)
    print(f"📄  Max pages: {MAX_PAGES} | Page wait: {PAGE_WAIT_MS}ms\n")

    domains = scrape()

    if not domains:
        print("❌  No domains collected.")
        input("\n⏸️  Press Enter to close...")
        return

    unique = write_canonical_csv(domains, 'greece.csv')
    print(f"\n📊  Total unique URLs written: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"⚠️  Only {len(unique)} — below expected minimum of {MIN_EXPECTED}.")

    print(f"\n🔍  First 20 URLs:")
    for u in unique[:20]:
        print(f"    {u}")
    if len(unique) > 20:
        print(f"    ... and {len(unique) - 20} more")

    print("\n✅  Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("\n💥  UNHANDLED ERROR:")
        traceback.print_exc()
    finally:
        input("\n⏸️  Press Enter to close...")
