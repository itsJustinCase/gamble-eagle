#!/usr/bin/env python3
"""
Romania Blacklist Scraper (ONJN)
=================================
Source: Oficiul Național pentru Jocuri de Noroc
        https://onjn.gov.ro/wp-content/uploads/Onjn.gov.ro/Acasa/BlackList/Lista-neagra.txt

ONJN blocks plain HTTP requests but allows real browser access.
Uses Playwright (same approach as fetch_romania.py) to load the page
and extract the raw text content.

Requirements:
    pip install playwright beautifulsoup4
    playwright install chromium

Outputs: romania_blacklist.csv (canonical format — timestamp line 1, one domain per line)
"""

import re
import os
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

SOURCE_URL   = "https://onjn-gov-ro.translate.goog/lista-neagra/?_x_tr_sl=auto&_x_tr_tl=en&_x_tr_hl=en&_x_tr_pto=wapp"
MIN_EXPECTED = 10
PAGE_WAIT_MS = 10000


def write_canonical_csv(domains, filepath):
    seen = set()
    unique = []
    for d in domains:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    unique.sort()
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for d in unique:
            f.write(d.strip() + '\n')
    print(f"💾  Saved {len(unique)} domains → {filepath}  (stamp: {stamp})")
    return unique


def clean_domain(raw):
    d = raw.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.rstrip('/')


def is_valid_domain(d):
    return bool(
        d and '.' in d and ' ' not in d
        and 3 < len(d) < 100
        and not d.startswith('.')
        and not d.startswith('#')
    )


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

        print(f"⏳  Waiting {PAGE_WAIT_MS}ms for page to settle...")
        page.wait_for_timeout(PAGE_WAIT_MS)

        title = page.title()
        print(f"    Page title: {title}")

        # The txt file renders as plain text in a <pre> tag in Chrome
        # Get the full page text content
        try:
            body_text = page.inner_text("body")
        except Exception:
            body_text = page.content()

        browser.close()
        return body_text


def main():
    print("=" * 60)
    print("🇷🇴  ROMANIA — ONJN Blacklist (Lista Neagră)")
    print("=" * 60)
    print("🌐  Using Playwright/Chromium\n")

    try:
        raw_text = scrape()
    except Exception as e:
        print(f"❌  Scraper failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"    Got {len(raw_text):,} chars of text")

    domains = []
    for line in raw_text.splitlines():
        cleaned = clean_domain(line)
        if is_valid_domain(cleaned):
            domains.append(cleaned)

    print(f"\n📊  Found {len(domains)} unique blacklisted domains")

    if not domains:
        print("❌  No domains found — page may not have loaded correctly")
        return

    if len(domains) < MIN_EXPECTED:
        print(f"❌  Only {len(domains)} — below minimum of {MIN_EXPECTED}, not writing")
        return

    print(f"\n🔍  First 10 entries:")
    for d in domains[:10]:
        print(f"    {d}")
    if len(domains) > 10:
        print(f"    ... and {len(domains) - 10} more")

    write_canonical_csv(domains, 'romania_blacklist.csv')
    print("\n✅  Done.")


if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
