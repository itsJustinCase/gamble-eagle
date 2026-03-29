#!/usr/bin/env python3
import re
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from bs4 import BeautifulSoup

try:
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo('Europe/Paris')
    def _paris_now(): return datetime.now(_PARIS)
except ImportError:
    import pytz
    _PARIS = pytz.timezone('Europe/Paris')
    def _paris_now(): return datetime.now(_PARIS)

URL = "https://onjn.gov.ro/licentiati-clasa-i/"
MIN_EXPECTED = 10

def fetch_page():
    print(f"🌐 Launching stealth browser to fetch {URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        stealth_sync(page)
        
        # High timeout to allow Cloudflare verification to pass
        page.goto(URL, wait_until="networkidle", timeout=90000)
        
        # Wait for the table to appear (signaling bypass success)
        try:
            page.wait_for_selector("table", timeout=30000)
            print("✅ Verification bypassed. Table found.")
        except Exception:
            print("❌ Failed to bypass verification or table not found.")
            
        html = page.content()
        browser.close()
        return html

def clean_domain(raw):
    d = raw.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.split('/')[0]

def is_valid_domain(d):
    return d and '.' in d and ' ' not in d and 4 < len(d) < 100

def extract_domains(html):
    soup = BeautifulSoup(html, 'html.parser')
    domains = set()

    for td in soup.find_all(['td', 'th', 'a']):
        text = td.get_text(strip=True) if not td.name == 'a' else td.get('href', '')
        matches = re.findall(r'\b([a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)\b', text)
        for m in matches:
            cleaned = clean_domain(m)
            if is_valid_domain(cleaned):
                domains.add(cleaned)

    exclude = {'onjn.gov.ro', 'gov.ro', 'wordpress.com', 'facebook.com', 'google.com'}
    return sorted(d for d in domains if d not in exclude and not d.endswith('.gov.ro'))

def main():
    try:
        html = fetch_page()
        domains = extract_domains(html)
        
        if len(domains) >= MIN_EXPECTED:
            stamp = _paris_now().strftime('%Y%m%d %H:%M')
            with open('romania.csv', 'w', encoding='utf-8') as f:
                f.write(f"{stamp}\n" + "\n".join(domains))
            print(f"💾 Saved {len(domains)} domains.")
        else:
            print(f"⚠️ Only found {len(domains)} domains. Check HTML output.")
    except Exception as e:
        print(f"❌ Execution failed: {e}")

if __name__ == "__main__":
    main()