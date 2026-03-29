#!/usr/bin/env python3
"""
Fetch France Gambling Sites - ALL .fr URLs
Extracts EVERY .fr domain from the page
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
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

def extract_all_fr_urls():
    """
    Extract ALL .fr domains from the ANJ page
    """
    url = "https://anj.fr/offre-de-jeu-et-marche/operateurs-agrees"
    
    try:
        print("🔍 Connecting to ANJ France website...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        print("✅ Page loaded successfully")
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("🔍 Extracting ALL .fr URLs from the entire page...")
        
        # Get ALL text content
        all_text = soup.get_text()
        
        # Extract EVERY .fr domain from the entire page.
        # The regex anchors on a word boundary at the start to avoid
        # picking up prefixes like =- from surrounding text (e.g. "=-zeturf.fr").
        all_fr_domains = re.findall(r'(?<![a-zA-Z0-9])([a-zA-Z0-9][a-zA-Z0-9.-]*\.fr)', all_text)
        
        # Remove duplicates and filter out non-gambling domains
        domains = set()
        excluded = ['anj.fr', 'service-public.fr', 'gov.fr']
        
        for domain in all_fr_domains:
            domain_lower = domain.lower()
            if not any(excluded_domain in domain_lower for excluded_domain in excluded):
                domains.add(domain_lower)
        
        # Sort for consistency
        sorted_domains = sorted(domains)
        
        return sorted_domains
        
    except requests.RequestException as e:
        print(f"❌ Error fetching the page: {e}")
        return []
    except Exception as e:
        print(f"❌ Error parsing the page: {e}")
        return []

def main():
    """Main function"""
    print("=" * 60)
    print("🇫🇷 FRANCE GAMBLING SITES - ALL .fr URLs")
    print("=" * 60)
    print("🌐 Source: https://anj.fr/offre-de-jeu-et-marche/operateurs-agrees")
    
    # Extract domains
    french_domains = extract_all_fr_urls()
    
    if not french_domains:
        print("❌ No domains found.")
        return
    
    print(f"\n🎯 Found {len(french_domains)} .fr domains:")
    print("=" * 50)
    
    for i, domain in enumerate(french_domains, 1):
        print(f"{i:2d}. {domain}")
    
    write_canonical_csv(french_domains, 'france.csv')
    print(f"📊 Total .fr domains: {len(french_domains)}")
    print("✅ Extraction complete!")

if __name__ == "__main__":
    main()