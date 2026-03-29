#!/usr/bin/env python3
"""
UK Licensed Gambling Sites Scraper
=====================================
Source: UK Gambling Commission
        https://www.gamblingcommission.gov.uk/publicregister/businesses/download

Downloads the business-licence-register.xlsx file directly.
Reads the 'DomainNames' sheet, column B (index 1) — one domain per row.
Skips the header row. Strips www. and protocol.

Requirements:
    pip install requests pandas openpyxl
"""

import re
import io
import requests
import pandas as pd
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

# ── Config ────────────────────────────────────────────────────────────────────

DOWNLOAD_URL = (
    "https://www.gamblingcommission.gov.uk/downloads/business-licence-register.xlsx"
)
SHEET_NAME   = "DomainNames"
DOMAIN_COL   = 1        # column B (0-based index)
MIN_EXPECTED = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, */*"
    ),
    "Referer": "https://www.gamblingcommission.gov.uk/",
}

# ── Canonical CSV writer ──────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
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
    print(f"💾  Saved {len(unique)} URLs → {filepath}  (stamp: {stamp})")
    return unique

# ── URL cleaner ───────────────────────────────────────────────────────────────

def clean_url(raw):
    """Strip protocol and www. Preserve paths and trailing slashes."""
    url = str(raw).strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇬🇧  UK LICENSED GAMBLING SITES SCRAPER (UKGC)")
    print("=" * 60)
    print(f"📥  Downloading: {DOWNLOAD_URL}\n")

    # Download the Excel file
    try:
        r = requests.get(DOWNLOAD_URL, headers=HEADERS, timeout=60)
        r.raise_for_status()
        print(f"✅  Downloaded {len(r.content):,} bytes (HTTP {r.status_code})")
    except Exception as e:
        print(f"❌  Download failed: {e}")
        return

    # Parse with pandas
    try:
        df = pd.read_excel(
            io.BytesIO(r.content),
            sheet_name=SHEET_NAME,
            header=0,           # row 0 is the header
            usecols=[DOMAIN_COL],
            dtype=str
        )
        print(f"✅  Sheet '{SHEET_NAME}' loaded: {len(df)} rows")
    except Exception as e:
        print(f"❌  Failed to read Excel: {e}")
        return

    # Extract and clean domains from column B
    col = df.iloc[:, 0]   # first (only) column we loaded
    urls = []
    skipped = 0

    for val in col:
        if pd.isna(val) or not str(val).strip():
            skipped += 1
            continue
        cleaned = clean_url(val)
        if cleaned and "." in cleaned and len(cleaned) > 3:
            urls.append(cleaned)
        else:
            skipped += 1

    print(f"📊  {len(urls)} domains extracted ({skipped} empty/invalid skipped)")

    if not urls:
        print("❌  No URLs found.")
        return

    unique = write_canonical_csv(urls, 'UK.csv')
    print(f"📊  Total unique URLs written: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"⚠️  Only {len(unique)} — below expected minimum of {MIN_EXPECTED}.")

    print(f"\n🔍  First 10 URLs:")
    for u in unique[:10]:
        print(f"    {u}")
    if len(unique) > 10:
        print(f"    ... and {len(unique) - 10} more")

    print("\n✅  Done.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print("\n💥  UNHANDLED ERROR:")
        traceback.print_exc()
    finally:
        input("\n⏸️  Press Enter to close...")
