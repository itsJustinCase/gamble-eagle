#!/usr/bin/env python3
import re
import os
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from bs4 import BeautifulSoup

# SETUP PATHS
# Forces the screenshot and CSV to the repository root
ROOT_DIR = os.getcwd() 
OUTPUT_PATH = os.path.join(ROOT_DIR, 'romania.csv')
SCREENSHOT_PATH = os.path.join(ROOT_DIR, 'cloudflare_block.png')

def fetch_page():
    url = "https://onjn.gov.ro/licentiati-clasa-i/"
    print(f"🌐 Target: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        stealth_sync(page)
        
        try:
            print("⏳ Attempting connection...")
            # We use 'commit' so it doesn't wait for the whole page to hang
            page.goto(url, wait_until="commit", timeout=20000)
            
            print("⏳ Connection made. Waiting 20s for content to render...")
            time.sleep(20)
            
            # Try to catch the table
            page.wait_for_selector("table", timeout=10000)
            print("✅ Table found.")
            
            html = page.content()
            browser.close()
            return html
            
        except Exception as e:
            print(f"⚠️ Process interrupted: {e}")
            # FORCE screenshot even if partially loaded
            try:
                page.screenshot(path=SCREENSHOT_PATH)
                print(f"📸 Diagnostic captured at: {SCREENSHOT_PATH}")
            except:
                print("❌ Could not even capture screenshot.")
            browser.close()
            sys.exit(1)

def main():
    html = fetch_page()
    if not html:
        sys.exit(1)
        
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

    exclude = {'onjn.gov.ro', 'gov.ro', 'wordpress.com', 'facebook.com', 'google.com'}
    final_list = sorted(d for d in domains if d not in exclude and not d.endswith('.gov.ro'))

    if len(final_list) >= 10:
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write(stamp + '\n' + '\n'.join(final_list))
        print(f"💾 Saved {len(final_list)} domains.")
    else:
        print(f"❌ Failed: Only found {len(final_list)} domains.")
        sys.exit(1)

if __name__ == "__main__":
    main()
