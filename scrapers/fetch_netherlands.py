#!/usr/bin/env python3
"""
Netherlands Licensed Gambling Sites Scraper
============================================
Uses Playwright on openovergokken.nl/kansspelwijzer/ to:
  1. Tick the "Online gokspel" filter
  2. Wait for cards to filter
  3. Scroll to load all lazy-loaded cards
  4. Parse and export to CSV

Columns in canonical output:
  - url: cleaned URL (no http://, no www.)

Requirements:
    pip install playwright beautifulsoup4
    playwright install chromium
"""

import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
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

URL = "https://openovergokken.nl/kansspelwijzer/"

# Minimum number of results expected — if fewer are found, treat as scrape failure
MIN_EXPECTED_RESULTS = 10


def write_canonical_csv(urls, filepath):
    """
    Write the canonical GambleEagle CSV format:
      Line 1: datetime stamp in Paris time — YYYYMMDD HH:MM
      Lines 2+: one clean URL per line, no header, no extra columns.
    URLs must already be clean (no http://, no www.).
    Trailing slashes preserved as-is.
    """
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in urls:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(urls)} URLs → {filepath}  (stamp: {stamp})")

# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_url(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r'[(){}\[\]]', '', text)  # Remove brackets
    text = re.sub(r'^https?://', '', text)
    text = re.sub(r'^www\.', '', text)
    return text.rstrip('/')

def split_urls(raw: str) -> list:
    parts = re.split(r'[,;\s]+', raw.strip())
    return [clean_url(p) for p in parts if '.' in p and len(p) > 3]

# ── Fetch ─────────────────────────────────────────────────────────────────────

def get_rendered_html() -> str:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="nl-NL",
        )

        # ── 1. Load page ──────────────────────────────────────────────────────
        print(f"🌐  Loading {URL} ...")
        page.goto(URL, wait_until="networkidle", timeout=30_000)
        print("✅  Page loaded.")

        # ── 2. Dismiss cookie banner ──────────────────────────────────────────
        for sel in [
            "button:has-text('Accepteren')", "button:has-text('Akkoord')",
            "button:has-text('Accept')",     "button:has-text('Alle cookies')",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2_000):
                    btn.click()
                    print("🍪  Cookie banner dismissed")
                    time.sleep(1)
                    break
            except:
                pass

        # ── 3. Wait for filter span and click it ──────────────────────────────
        print("☑️   Waiting for 'Online gokspel' filter...")
        try:
            filter_span = page.locator("span.jet-checkboxes-list__label", has_text="Online gokspel")
            filter_span.first.wait_for(state="visible", timeout=15_000)
            print("    ✓ Filter found — clicking...")
            filter_span.first.click()
            print("    ✓ 'Online gokspel' ticked")
            time.sleep(4)  # Wait for filtered cards to render
        except PlaywrightTimeoutError:
            # Debug: dump all jet-checkboxes-list__label spans found
            all_spans = page.locator("span.jet-checkboxes-list__label").all()
            print(f"    ⚠️  Timed out. Found {len(all_spans)} filter spans on page:")
            for s in all_spans:
                try:
                    print(f"       · {repr(s.inner_text())}")
                except:
                    pass
            print("    Saving debug_page.html...")
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            browser.close()
            return ""

        # ── 4. Wait for filtered cards to appear ──────────────────────────────
        print("⏳  Waiting for filtered cards...")
        try:
            page.wait_for_selector("div.category-online-gokspel", timeout=15_000)
            print("    ✓ Filtered cards detected")
        except PlaywrightTimeoutError:
            print("    ⚠️  Filtered cards not detected — saving debug_page.html")
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            browser.close()
            return ""

        # ── 5. Scroll to load all lazy-loaded cards ───────────────────────────
        print("📜  Scrolling to load all cards...")
        prev_count = 0
        stale = 0
        for _ in range(100):
            page.evaluate("window.scrollBy(0, 500)")
            time.sleep(0.3)
            count = page.locator("div.category-online-gokspel").count()
            if count == prev_count:
                stale += 1
                if stale >= 8:
                    print(f"    ✓ Stable at {count} cards")
                    break
            else:
                stale = 0
                prev_count = count

        html = page.content()
        print(f"📄  Captured {len(html):,} bytes of rendered HTML")
        browser.close()
        return html

# ── Parse ─────────────────────────────────────────────────────────────────────

def parse_cards(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.category-online-gokspel")
    print(f"📦  Found {len(cards)} 'Online gokspel' cards")

    results = []
    for card in cards:
        h3  = card.select_one("h3.elementor-heading-title")
        h2s = card.select("h2.elementor-heading-title")

        if not h3 or not h2s:
            continue

        entity   = h3.get_text(strip=True)
        websites = h2s[0].get_text(strip=True) if len(h2s) >= 1 else ""
        url_raw  = h2s[1].get_text(strip=True) if len(h2s) >= 2 else websites

        # Collect URLs from heading text (primary source)
        text_urls = split_urls(url_raw)

        # Also collect URLs from any anchor hrefs within the card.
        # This catches path-based entries (e.g. casino.toto.nl/winn-itt)
        # that may be linked but not cleanly present in heading text.
        # Exclude hrefs pointing back to openovergokken.nl itself (operator detail pages).
        href_urls = []
        for a in card.select("a[href]"):
            href = a.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("mailto"):
                continue
            if "openovergokken.nl" in href:
                continue
            cleaned = clean_url(href)
            if cleaned and "." in cleaned and len(cleaned) > 3:
                href_urls.append(cleaned)

        # Merge: text URLs first, then any href URLs not already present
        seen_in_card = set(text_urls)
        all_urls = text_urls[:]
        for u in href_urls:
            if u not in seen_in_card:
                seen_in_card.add(u)
                all_urls.append(u)

        for url in all_urls:
            results.append({"entity": entity, "websites": websites, "url": url})
            print(f"  🎯  {entity[:45]:<45}  {websites[:25]:<25}  →  {url}")

    return results

# ── Save ──────────────────────────────────────────────────────────────────────

def save_canonical(records: list) -> list:
    """Deduplicate records by URL and write canonical CSV. Returns unique records."""
    seen = set()
    unique = [r for r in records if not (r["url"] in seen or seen.add(r["url"]))]

    if len(unique) < MIN_EXPECTED_RESULTS:
        print(f"❌  Only {len(unique)} results found — below minimum of {MIN_EXPECTED_RESULTS}.")
        print("    Aborting write to avoid overwriting good data with a bad scrape.")
        return []

    urls = [r["url"] for r in unique]
    write_canonical_csv(urls, 'netherlands.csv')
    return unique

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇳🇱  NETHERLANDS LICENSED GAMBLING SITES SCRAPER")
    print("=" * 60)

    html = get_rendered_html()
    if not html:
        print("❌  Could not get rendered HTML — check debug_page.html")
        return

    records = parse_cards(html)
    if not records:
        print("❌  No records found — check debug_page.html")
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        return

    unique = save_canonical(records)
    if not unique:
        return

    print(f"\n📋  Preview (first 10 rows):")
    print(f"  {'Entity':<45} {'Websites':<25} URL")
    print("  " + "-" * 95)
    for r in unique[:10]:
        print(f"  {r['entity'][:44]:<45} {r['websites'][:24]:<25} {r['url']}")

    print(f"\n📊  Total unique URLs: {len(unique)}")
    print("✅  Done.")

if __name__ == "__main__":
    main()
