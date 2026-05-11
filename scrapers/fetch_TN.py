#!/usr/bin/env python3
"""
Tennessee Licensed Sports Wagering Operators Scraper
=====================================================
Source: https://www.tn.gov/swac/licensees-registrants.html
Tab: "Sports Wagering Operator – Website and Contact Information" (tab 4)

Output CSV columns:
    operator  — brand name (e.g. "BetMGM")
    url       — clean domain from the website hyperlink

Requirements:
    pip install playwright beautifulsoup4
    playwright install chromium
"""

import csv
import re
import time
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL         = "https://www.tn.gov/swac/licensees-registrants.html"
OUTPUT_FILE = "TN.csv"

# Exact tab button and panel IDs from the page source
TAB_BUTTON_ID = "tab-02625c97b9ed49888d9fc8ae60ae8d56-3"
TAB_PANEL_ID  = "tabpanel-02625c97b9ed49888d9fc8ae60ae8d56-3"

# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_url(raw: str) -> str:
    url = raw.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url.rstrip('/')

# ── Fetch ─────────────────────────────────────────────────────────────────────

def get_tab_html() -> str:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )

        print(f"🌐  Loading {URL} ...")
        page.goto(URL, wait_until="networkidle", timeout=30_000)
        print("✅  Page loaded.")
        time.sleep(2)

        # Click the exact tab button by ID
        print("🖱️   Clicking tab 4 by ID...")
        try:
            page.locator(f"#{TAB_BUTTON_ID}").click(timeout=10_000)
            print("    ✓ Tab clicked by ID")
        except PlaywrightTimeoutError:
            # Fallback: click by visible text
            print("    ↩️  Trying text fallback...")
            page.locator("text=Sports Wagering Operator").last.click(timeout=10_000)
            print("    ✓ Tab clicked by text")

        # Wait for any tab panel containing "Website:" to become visible
        print("⏳  Waiting for tab content to render...")
        try:
            page.wait_for_selector("text=Website:", timeout=15_000)
            print("    ✓ Website content detected")
        except PlaywrightTimeoutError:
            print("    ⚠️  Still continuing...")
        time.sleep(3)

        # Find the active/visible tab panel — try multiple strategies
        html = ""
        # Strategy 1: panel with class "show active"
        try:
            panel = page.locator(".tab-pane.show.active, .tab-pane.active")
            if panel.count() > 0:
                html = panel.first.inner_html()
                print(f"    ✓ Got active panel via .tab-pane.active")
        except: pass

        # Strategy 2: any visible tabpanel role containing "Website:"
        if not html or len(html) < 200:
            try:
                panel = page.locator("[role='tabpanel']").filter(has_text="Bally")
                if panel.count() > 0:
                    html = panel.first.inner_html()
                    print(f"    ✓ Got panel via tabpanel+Bally filter")
            except: pass

        # Strategy 3: full page as last resort
        if not html or len(html) < 200:
            html = page.content()
            print("    ⚠️  Falling back to full page content")

        print(f"📄  Captured {len(html):,} bytes")
        with open("debug_TN.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("    Debug saved → debug_TN.html")
        browser.close()
        return html
        print("    Debug saved → debug_TN.html")

        browser.close()
        return html

# ── Parse ─────────────────────────────────────────────────────────────────────

def parse_operators(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Structure: <h2>BetMGM:</h2> ... <p>Website: <a href="...">...</a></p>
    headings = soup.find_all(["h2", "h3", "h4"])

    for heading in headings:
        operator = heading.get_text(strip=True).rstrip(':').strip()
        if not operator or len(operator) < 2:
            continue

        website_url = None
        # Walk siblings until next heading
        for sibling in heading.find_next_siblings():
            if sibling.name in ["h2", "h3", "h4"]:
                break
            text = sibling.get_text(separator=" ", strip=True)
            if "website" in text.lower():
                link = sibling.find("a", href=True)
                if link:
                    website_url = clean_url(link["href"])
                    break

        op_lower = operator.lower()

        # Penn Sports Interactive → funky urldefense link, override with correct URL
        if "penn sports" in op_lower or "thescore" in op_lower:
            website_url = "espnbet.com"

        # Fanatics Sportsbook → no link on page, hardcode
        if "fanatics" in op_lower:
            website_url = "betfanatics.com/sportsbook"

        results.append({"operator": operator, "url": website_url or ""})
        if website_url:
            print(f"  🎯  {operator:<35}  →  {website_url}")
        else:
            print(f"  ⚠️   {operator:<35}  →  (no website found)")

        # VIP Play → add second URL as extra row
        if "vip play" in op_lower:
            results.append({"operator": operator, "url": "vipplayinc.com"})
            print(f"  🎯  {operator:<35}  →  vipplayinc.com (extra)")

    return results

# ── Save ──────────────────────────────────────────────────────────────────────

def save_csv(records: list, filename: str):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["operator", "url"])
        writer.writeheader()
        writer.writerows(records)
    print(f"\n💾  Saved {len(records)} rows → {filename}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇺🇸  TENNESSEE SPORTS WAGERING OPERATORS SCRAPER")
    print("=" * 60)

    html = get_tab_html()

    if not html or len(html) < 500:
        print("❌  Tab content too small — check debug_TN.html")
        return

    records = parse_operators(html)

    if not records:
        print("❌  No operators parsed — check debug_TN.html")
        return

    save_csv(records, OUTPUT_FILE)

    print(f"\n📋  Results:")
    print(f"  {'Operator':<35} URL")
    print("  " + "-" * 70)
    for r in records:
        print(f"  {r['operator']:<35} {r['url']}")

    print(f"\n📊  Total: {len(records)} operators")
    print("✅  Done.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress [RETURN] to exit...")
