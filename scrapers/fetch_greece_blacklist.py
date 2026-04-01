#!/usr/bin/env python3
"""
Greece Blacklist Scraper (HGC)
==============================
Source: Hellenic Gaming Commission
        https://www.gamingcommission.gov.gr/images/epopteia-kai-elegxos/blacklist/blacklist_en.xlsx

Excel structure:
  Row 1: Title row ("Hellenic Gaming Commission -- CATALOG (Blacklist...)")
  Row 2: Column headers (A/A, A/M, WEBSITE, DOMAIN NAME, ...)
  Row 3+: Data

We use column D (DOMAIN NAME) — already clean, no www. prefix.

Outputs: greece_blacklist.csv (canonical format — timestamp line 1, one domain per line)
"""

import re
import os
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

URL          = "https://www.gamingcommission.gov.gr/images/epopteia-kai-elegxos/blacklist/blacklist_en.xlsx"
MIN_EXPECTED = 10

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://www.gamingcommission.gov.gr/',
}


def write_canonical_csv(domains, filepath):
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for d in sorted(set(domains)):
            f.write(d.strip() + '\n')
    print(f"💾  Saved {len(domains)} domains → {filepath}  (stamp: {stamp})")


def clean_domain(raw):
    d = str(raw).strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    # Remove any path after the domain
    d = d.split('/')[0]
    return d.strip()


def is_valid_domain(d):
    return bool(
        d and d != 'nan' and '.' in d
        and ' ' not in d and 3 < len(d) < 100
        and not d.startswith('.')
    )


def fetch_blacklist():
    print(f"🌐  Downloading HGC blacklist Excel file...")
    for attempt in range(1, 4):
        try:
            print(f"    Attempt {attempt}/3...")
            resp = requests.get(URL, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            print(f"    ✅  HTTP {resp.status_code} — {len(resp.content):,} bytes")
            break
        except Exception as e:
            print(f"    ⚠️  {e}")
            if attempt == 3:
                raise

    print("    📊  Parsing Excel file...")

    # Row 1 is a title row, row 2 is the actual header — so header=1 (0-indexed)
    df = pd.read_excel(io.BytesIO(resp.content), engine='openpyxl', header=1)

    print(f"    Columns: {list(df.columns)}")
    print(f"    Rows: {len(df)}")
    print(f"    First 3 rows of data:\n{df.head(3).to_string()}")

    # Find DOMAIN NAME column
    domain_col = None
    for col in df.columns:
        if 'domain' in str(col).lower():
            domain_col = col
            break

    if domain_col is None:
        # Fallback: try column D by position (index 3)
        print("    ⚠️  'DOMAIN NAME' column not found by name — using column index 3")
        domain_col = df.columns[3]

    print(f"    Using column: '{domain_col}'")

    domains = set()
    skipped = 0
    for val in df[domain_col].dropna():
        cleaned = clean_domain(val)
        if is_valid_domain(cleaned):
            domains.add(cleaned)
        else:
            skipped += 1

    print(f"    {len(domains)} valid domains, {skipped} skipped")
    return sorted(domains)


def main():
    print("=" * 60)
    print("🇬🇷  GREECE — HGC Blacklist")
    print("=" * 60)

    try:
        blacklist = fetch_blacklist()
    except Exception as e:
        print(f"❌  Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n📊  Found {len(blacklist)} unique blacklisted domains")

    if not blacklist:
        print("❌  No domains found")
        return

    if len(blacklist) < MIN_EXPECTED:
        print(f"❌  Only {len(blacklist)} — below minimum of {MIN_EXPECTED}, not writing")
        return

    print(f"\n🔍  First 10 entries:")
    for d in blacklist[:10]:
        print(f"    {d}")
    if len(blacklist) > 10:
        print(f"    ... and {len(blacklist) - 10} more")

    write_canonical_csv(blacklist, 'greece_blacklist.csv')
    print("✅  Done.")


if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
