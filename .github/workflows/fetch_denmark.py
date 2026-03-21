#!/usr/bin/env python
"""
Fetch Denmark gambling sites - 
Captures exactly what's shown on the live Spillemyndigheden website
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import unicodedata
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

def clean_domain(domain):
    """
    Clean domain by removing www. but KEEPING paths like /dk
    """
    # Remove www. prefix if present but keep everything else
    if domain.startswith('www.'):
        domain = domain[4:]
    
    return domain

def extract_danish_sites_live():
    """
    Extract licensed gambling domains from the Spillemyndigheden website
    """
    url = "https://www.spillemyndigheden.dk/tilladelsesindehavere/print"
    
    try:
        print("Connecting to Spillemyndigheden website...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print("Live website loaded successfully")
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the main table
        table = soup.find('table')
        if not table:
            print("No table found on the page")
            return []
        
        print("Live table found, extracting current data...")
        
        # Use a dictionary to track lowercase versions and keep the original case
        domain_dict = {}
        
        # Find all table rows
        rows = table.find_all('tr')
        
        # Skip header row and process data rows
        for row in rows[1:]:  # Skip header row
            cells = row.find_all('td')
            
            if len(cells) >= 1:  # Ensure we have enough columns
                # The last cell contains the URLs (Domæner column)
                url_cell = cells[-1]
                
                # Get the text content with proper encoding
                urls_text = url_cell.get_text()
                
                # Pattern to capture domains with paths, including special characters
                pattern = r'\b(?:https?://)?(?:www\.)?([a-zA-Z0-9æøåÆØÅ](?:[a-zA-Z0-9æøåÆØÅ\-]*[a-zA-Z0-9æøåÆØÅ])?\.[a-zA-ZæøåÆØÅ]{2,}(?:\.[a-zA-ZæøåÆØÅ]{2,})?(?:/[a-zA-Z0-9æøåÆØÅ\-._~%!$&\'()*+,;=:@/?]*)?)\b'
                
                found_entries = re.findall(pattern, urls_text)
                
                for entry in found_entries:
                    # Clean the domain (remove www. but KEEP paths)
                    cleaned_entry = clean_domain(entry)
                    
                    if is_valid_gambling_domain(cleaned_entry):
                        # Use lowercase as key for deduplication, but keep original case
                        lowercase_key = cleaned_entry.lower()
                        if lowercase_key not in domain_dict:
                            domain_dict[lowercase_key] = cleaned_entry
                            print(f"Found: {cleaned_entry}")
        
        # Also check for any domains we might have missed in the entire page
        all_text = soup.get_text()
        additional_entries = re.findall(pattern, all_text)
        for entry in additional_entries:
            cleaned_entry = clean_domain(entry)
            
            if is_valid_gambling_domain(cleaned_entry):
                lowercase_key = cleaned_entry.lower()
                if lowercase_key not in domain_dict:
                    domain_dict[lowercase_key] = cleaned_entry
                    print(f"Found additional: {cleaned_entry}")
        
        # Get the final domains (keeping the original case from first occurrence)
        final_domains = list(domain_dict.values())
        
        # Remove specific unwanted domains (check if they appear in any entry)
        domains_to_remove = ['swush.com', 'c.mail', 'royalcasino.com']
        final_domains = [domain for domain in final_domains 
                        if not any(remove_domain in domain.lower() for remove_domain in domains_to_remove)]
        
        # Sort the domains
        sorted_domains = sorted(final_domains)
        
        print(f"\nFinal domain count: {len(sorted_domains)}")
        print("Removed unwanted domains: swush.com, c.mail, royalcasino.com")
        print("Removed case-insensitive duplicate domains")
        print("Preserved paths in domains (e.g., netbet.com/dk)")
        print("Preserved special characters (e.g., rød25.dk)")
        
        return sorted_domains
        
    except Exception as e:
        print(f"Error: {e}")
        return []

def is_valid_gambling_domain(entry):
    """Validate if this entry should be included"""
    # Must contain a proper domain with TLD
    if '.' not in entry:
        return False
    
    # Must have at least 2 characters after the last dot (like .dk, .com)
    parts = entry.split('.')
    if len(parts) < 2 or len(parts[-1]) < 2:
        return False
    
    # Filter out obvious non-gambling entries
    bad_keywords = ['spillemyndigheden', 'example', 'test', 'mail.']
    if any(bad in entry.lower() for bad in bad_keywords):
        return False
    
    return True

def main():
    """Main function"""
    print("=" * 50)
    print("DENMARK GAMBLING SITES SCRAPER")
    print("=" * 50)
    
    # Extract domains
    danish_domains = extract_danish_sites_live()
    
    if not danish_domains:
        print("No domains found.")
        return
    
    print(f"\nFound {len(danish_domains)} current Danish gambling domains")
    print("-" * 50)
    
    for i, domain in enumerate(danish_domains, 1):
        print(f"{i}. {domain}")
    
    write_canonical_csv(danish_domains, 'denmark.csv')
    print(f"Total: {len(danish_domains)} domains")
    print("\nNote: Removed 'swush.com', 'c.mail', and 'royalcasino.com'")
    print("Removed case-insensitive duplicate domains (Bingo.dk and bingo.dk treated as same)")
    print("Cleaned 'www.' prefixes but preserved paths (e.g., netbet.com/dk)")
    print("Preserved special characters like 'ø' in domains")

if __name__ == "__main__":
    main()