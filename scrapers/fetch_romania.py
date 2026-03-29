#!/usr/bin/env python3
import re
import os
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from bs4 import BeautifulSoup

# Setup Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, 'romania.csv')
SCREENSHOT_PATH = os.path.join(BASE_DIR, 'cloudflare_block.png')

# Timezone
try:
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo('Europe/Paris')
except ImportError:
    import pytz
    _PARIS = pytz.timezone('Europe/Paris')

def fetch_page():
    url = "https://onjn.gov.ro/licentiati-clasa-i/"
    print(f"🌐 Launching stealth browser for {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        stealth_sync(page)
        
        try:
            # 1. Load page
            print("⏳ Loading page...")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 2. Wait for Cloudflare "Verifying" to finish
            print("⏳ Waiting 15s for Cloudflare JS challenge...")
            time.sleep(15)
            
            # 3. Look for the table
            page.wait_for_selector("table", timeout=45000)
            print("✅ Bypass successful. Table found.")
            
            html = page.content()
            browser.close()
            return html
            
        except Exception as e:
            print(f"❌ Error during fetch: {e}")
            page.screenshot(path=SCREENSHOT_PATH)
            print(f"📸 Screenshot saved to {SCREENSHOT_PATH}")
            browser.close()
            sys.exit(1)

def main():
    html = fetch_page()
    soup = BeautifulSoup(html, 'html.parser')
    domains = set()

    # Extract from table cells and links
    for el in soup.find_all(['td', 'a']):
        text = el.get('href') if el.name == 'a' else el.get_text(strip=True)
        if not text: continue
        found = re.findall(r'\b([a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)\b', text)
        for m in found:
            clean = re.sub(r'^https?://(www\.)?', '', m.strip().lower()).split('/')[0]
            if '.' in clean and len(clean) > 4:
                domains.add(clean)

    exclude = {'onjn.gov.ro', 'gov.ro', 'wordpress.com', 'facebook.com', 'google.com', 'w.org'}
    final_list = sorted(d for d in domains if d not in exclude and not d.endswith('.gov.ro'))

    if len(final_list) >= 10:
        stamp = datetime.now(_PARIS).strftime('%Y%m%d %H:%M') if 'zoneinfo' in sys.modules else datetime.now(pytz.timezone('Europe/Paris')).strftime('%Y%m%d %H:%M')
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write(stamp + '\n' + '\n'.join(final_list))
        print(f"💾 Saved {len(final_list)} domains to {OUTPUT_PATH}")
    else:
        print(f"❌ Extraction failed: Found only {len(final_list)} domains.")
        sys.exit(1)

if __name__ == "__main__":
    main()
