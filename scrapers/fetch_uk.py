#!/usr/bin/env python3
"""
UK Licensed Gambling Sites Scraper (CSV Version)
=====================================
Source: UK Gambling Commission
        https://www.gamblingcommission.gov.uk/downloads/business-licence-register-domain-names.csv

Logic:
1. Downloads CSV.
2. Filters for Status='Active' OR Status='White Label'.
3. Removes any row where Status='Inactive'.
4. Outputs unique cleaned URLs to UK.csv with date header.
5. Remains open until user interaction.
"""

import re
import io
import requests
import pandas as pd
from datetime import datetime

# Handle timezone for Paris stamp
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

# ── Config ────────────────────────────────────────────────────────────────────

DOWNLOAD_URL = "https://www.gamblingcommission.gov.uk/downloads/business-licence-register-domain-names.csv"
MIN_EXPECTED = 100

# Status strings as defined by user
STATUS_ACTIVE = "active"
STATUS_WHITELABEL = "white label"
STATUS_INACTIVE = "inactive"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.gamblingcommission.gov.uk/",
}

# ── Helper Functions ──────────────────────────────────────────────────────────

def clean_url(raw):
    """Strip protocol and www. Preserve paths and trailing slashes."""
    url = str(raw).strip()
    url = re.sub(r'^https?://', '', url, flags=re.IGNORECASE)
    url = re.sub(r'^www\.', '', url, flags=re.IGNORECASE)
    return url

def write_canonical_csv(urls, filepath):
    """Writes sorted unique URLs with a date header."""
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    unique.sort()
    
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in unique:
            f.write(url.strip() + '\n')
    
    print(f"💾 Saved {len(unique)} URLs -> {filepath}")
    return unique

# ── Processing Logic ──────────────────────────────────────────────────────────

def fetch_and_process():
    print(f"🚀 Fetching: {DOWNLOAD_URL}")
    
    # Download
    resp = requests.get(DOWNLOAD_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    
    # Load CSV
    try:
        df = pd.read_csv(io.BytesIO(resp.content), encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(io.BytesIO(resp.content), encoding='latin-1')

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    
    # Map required columns
    domain_col = 'domain name' if 'domain name' in df.columns else df.columns[0]
    status_col = 'status'

    # Filter Setup
    df[status_col] = df[status_col].astype(str).str.lower().str.strip()

    # Logic: (Active OR White Label) AND NOT Inactive
    mask = (
        ((df[status_col] == STATUS_ACTIVE) | (df[status_col] == STATUS_WHITELABEL)) & 
        (df[status_col] != STATUS_INACTIVE)
    )
    
    filtered_df = df[mask]
    print(f"📊 Rows after filtering: {len(filtered_df)}")

    # Extract and clean
    urls = []
    for val in filtered_df[domain_col]:
        if pd.isna(val):
            continue
        cleaned = clean_url(val)
        if cleaned and "." in cleaned and len(cleaned) > 3:
            urls.append(cleaned)

    if not urls:
        print("❌ No valid URLs found after filtering.")
        return

    unique = write_canonical_csv(urls, 'UK.csv')
    
    if len(unique) < MIN_EXPECTED:
        print(f"⚠️ Warning: Found {len(unique)} URLs, lower than expected {MIN_EXPECTED}.")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        fetch_and_process()
        print("\n✅ Execution complete.")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "="*30)
        input("Press RETURN to exit...")