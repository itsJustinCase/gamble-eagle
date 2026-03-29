#!/usr/bin/env python
"""
Fetch Canada gambling sites from iGaming Ontario
Captures all links from play buttons without any deduplication or filtering
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

def extract_canadian_sites_raw():
    """
    Extract URLs from play buttons - no deduplication, no filtering
    """
    url = "https://igamingontario.ca/en/player/regulated-igaming-market"
    
    try:
        print("Connecting to iGaming Ontario website...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print("Page loaded successfully")
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        play_data = []
        
        # Find elements that contain "Play" text at the start
        play_elements = soup.find_all(string=re.compile(r'^Play', re.IGNORECASE))
        
        print(f"Found {len(play_elements)} play button elements")
        
        for element in play_elements:
            button_text = element.strip()
            
            # Get the parent element
            parent = element.parent
            
            # Look for href in the direct parent or nearby
            href = None
            
            # Check if parent is an a tag
            if parent.name == 'a' and parent.get('href'):
                href = parent.get('href')
            
            # If not, look in the parent container
            elif parent:
                # Look for any a tag in the parent container
                link = parent.find('a', href=True)
                if link:
                    href = link.get('href')
            
            # If we found a href, clean it minimally
            if href and href.startswith('http'):
                # Only remove http:// https:// and www. - keep everything else
                clean_url = href
                clean_url = re.sub(r'^https://', '', clean_url)
                clean_url = re.sub(r'^http://', '', clean_url)
                clean_url = re.sub(r'^www\.', '', clean_url)
                clean_url = clean_url.lower()
                # Ensure a slash separates the hostname from any query string.
                # e.g. on.bet365.ca?foo=1 → on.bet365.ca/?foo=1
                clean_url = re.sub(r'^([^/?#]+)(\?)', r'\1/\2', clean_url)
                
                play_data.append({
                    'button_text': button_text,
                    'original_url': href,
                    'clean_url': clean_url
                })
                print(f"  {button_text} - {clean_url}")
            else:
                print(f"  {button_text} - NO URL")
        
        return play_data
        
    except Exception as e:
        print(f"Error: {e}")
        return []

def main():
    """Main function"""
    print("=" * 50)
    print("CANADA GAMBLING SITES (ONTARIO)")
    print("=" * 50)
    
    # Extract domains
    print("Extracting URLs from play buttons...")
    play_data = extract_canadian_sites_raw()
    
    if not play_data:
        print("No play button URLs found.")
        return
    
    print(f"\nFound {len(play_data)} play button URLs (no deduplication)")
    print("-" * 50)
    
    # Count unique button texts to see if there are duplicates
    button_texts = [item['button_text'] for item in play_data]
    unique_button_texts = set(button_texts)
    
    print(f"Unique button texts: {len(unique_button_texts)}")
    print(f"Total button elements: {len(play_data)}")
    
    if len(unique_button_texts) != len(play_data):
        print(f"  Found {len(play_data) - len(unique_button_texts)} duplicate button texts")
    
    for i, item in enumerate(play_data, 1):
        print(f"{i}. {item['button_text']} - {item['clean_url']}")
    
    # Extract clean URLs and write canonical CSV
    clean_urls = [item['clean_url'] for item in play_data]
    write_canonical_csv(clean_urls, 'ontario.csv')
    print(f"Total URLs captured: {len(play_data)}")

if __name__ == "__main__":
    main()