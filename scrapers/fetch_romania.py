#!/usr/bin/env python3
import re
import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from bs4 import BeautifulSoup

# Force output to the repository root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, 'romania.csv')

def fetch_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = context.new_page()
        stealth_sync(page)
        
        print("🌐 Navigating to ONJN...")
        try:
            page.goto("https://onjn.gov.ro/licentiati-clasa-i/", wait_until="networkidle", timeout=90000)
            page.wait_for_selector("table", timeout=30000)
            print("✅ Table detected.")
        except Exception as e:
            print(f"❌ Page load failed: {e}")
            browser.close()
            sys.exit(1)
            
        html = page.content()
        browser.close()
        return html

def main():
    html = fetch_page()
    soup = BeautifulSoup(html, 'html.parser')
    domains = set()

    for el in soup.find_all(['td', 'a']):
        text = el.get('href') if el.name == 'a' else el.get_text(strip=True)
        if not text: continue
        found = re.findall(r'\b([a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)\b', text)
        for m in found:
            clean = re.sub(r'^https?://(www\.)?', '', m.strip().lower()).split('/')[0]
            if '.' in clean and len(clean) > 4:
                domains.add(clean)

    exclude = {'onjn.gov.ro', 'gov.ro', 'wordpress.com', 'facebook.com', 'google.com', 'w.org', 'jquery.com'}
    final_list = sorted(d for d in domains if d not in exclude and not d.endswith('.gov.ro'))

    if len(final_list) >= 10:
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write(datetime.now().strftime('%Y%m%d %H:%M') + '\n')
            f.write('\n'.join(final_list))
        print(f"✅ Success: {len(final_list)} domains saved to {OUTPUT_PATH}")
    else:
        print(f"❌ Failed: Only found {len(final_list)} domains.")
        sys.exit(1)

if __name__ == "__main__":
    main()
