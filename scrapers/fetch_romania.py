#!/usr/bin/env python3
"""
Romania Licensed Gambling Sites Scraper
========================================
Source: Oficiul Național pentru Jocuri de Noroc (ONJN)
        https://onjn.gov.ro/licentiati-clasa-i/

The ONJN site serves a JavaScript challenge page (Cloudflare or equivalent)
that returns 503 to all HTTP clients including curl_cffi. Playwright with a
real Chromium browser solves the challenge automatically and renders the page.

The page has a table of licensed operators. The column
"Sediu social, date de identificare" contains company address,
registration details, and one or more domain names (www.xxx.ro etc.)
listed after a "Domeniu:" label. We extract every domain from that column.

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

SOURCE_URL   = "https://onjn-gov-ro.translate.goog/licentiati-clasa-i/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp"
MIN_EXPECTED = 5
PAGE_WAIT_MS = 120000    # generous wait for challenge + page render

# Domains to exclude — government/admin sites that appear in address text
EXCLUDED_DOMAINS = {
    "onjn.gov.ro", "gov.ro", "anaf.ro", "registrul.ro",
    "example.com", "test.com",
}

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

# ── Domain pattern ────────────────────────────────────────────────────────────

# Match www.something.tld or something.ro/.com etc.
DOMAIN_PATTERN = re.compile(
    r'\bwww\.[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
    r'|'
    r'\b[a-zA-Z0-9][a-zA-Z0-9-]+\.[a-zA-Z]{2,3}\b',
    re.IGNORECASE
)

def extract_domains_from_text(text):
    matches = DOMAIN_PATTERN.findall(text)
    results = []
    for m in matches:
        cleaned = clean_url(m)
        if (cleaned
                and cleaned not in EXCLUDED_DOMAINS
                and "." in cleaned
                and all(p for p in cleaned.split("."))):
            results.append(cleaned)
    return results

# ── Column detector ───────────────────────────────────────────────────────────

def find_sediu_column_index(header_row):
    """Find the 'Sediu social' / 'Domeniu' column index from the header row."""
    for i, cell in enumerate(header_row.find_all(["th", "td"])):
        text = cell.get_text(strip=True).lower()
        if "sediu" in text or "domeniu" in text or "website" in text:
            return i
    return None

# ── Page extractor ────────────────────────────────────────────────────────────

def extract_urls_from_html(html):
    """
    Parse rendered HTML and extract all domains from the Sediu social column.
    Falls back to scanning all cells if the column can't be identified.
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = []

    table = soup.find("table")
    if not table:
        print("    ⚠️  No table found in rendered HTML.")
        return urls

    rows = table.find_all("tr")
    if not rows:
        print("    ⚠️  Table has no rows.")
        return urls

    header_row = rows[0]
    sediu_col = find_sediu_column_index(header_row)

    if sediu_col is not None:
        print(f"    ✓ 'Sediu social' column at index {sediu_col}")
        data_rows = rows[1:]
    else:
        print("    ⚠️  Column header not detected — scanning all cells.")
        data_rows = rows

    seen = set()
    for row in data_rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        if sediu_col is not None and len(cells) > sediu_col:
            cell_text = cells[sediu_col].get_text(separator="\n", strip=True)
            domains = extract_domains_from_text(cell_text)
        else:
            domains = []
            for cell in cells:
                domains.extend(extract_domains_from_text(
                    cell.get_text(separator="\n", strip=True)
                ))

        for d in domains:
            if d not in seen:
                seen.add(d)
                urls.append(d)
                print(f"  Found: {d}")

    return urls

# ── Scraper ───────────────────────────────────────────────────────────────────

def scrape():
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
            locale="ro-RO",
        )

        print(f"🌐  Loading {SOURCE_URL} ...")
        try:
            page.goto(SOURCE_URL, wait_until="networkidle", timeout=60_000)
        except Exception as e:
            print(f"    ⚠️  networkidle timeout — continuing anyway ({e})")

        # Extra wait for JS challenge to complete and page to render
        print(f"⏳  Waiting {PAGE_WAIT_MS}ms for challenge + render...")
        page.wait_for_timeout(PAGE_WAIT_MS)

        # Check we actually got a real page (not still on challenge)
        title = page.title()
        print(f"    Page title: {title}")

        # Wait for a table to appear
        try:
            page.wait_for_selector("table", timeout=15_000)
            print("    ✓ Table detected")
        except PlaywrightTimeoutError:
            print("    ⚠️  No table found — page may still be on challenge screen.")
            # Save debug HTML
            with open("debug_romania.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("    💾  Saved debug_romania.html for inspection.")
            browser.close()
            return []

        html = page.content()
        browser.close()

    return extract_urls_from_html(html)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇷🇴  ROMANIA LICENSED GAMBLING SITES SCRAPER (ONJN)")
    print("=" * 60)
    print("🌐  Using Playwright/Chromium to bypass JS challenge\n")

    urls = scrape()

    if not urls:
        print("❌  No URLs found — check debug_romania.html if it was created.")
        return

    unique = write_canonical_csv(urls, 'romania.csv')
    print(f"\n📊  Total unique URLs written: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"⚠️  Only {len(unique)} — below expected minimum of {MIN_EXPECTED}.")

    print(f"\n🔍  All URLs:")
    for u in unique:
        print(f"    {u}")

    print("\n✅  Done.")

if __name__ == "__main__":
    main()
