#!/usr/bin/env python3
"""
Australia Blocked Gambling Websites Scraper (ACMA)
===================================================
Source: Australian Communications and Media Authority
        https://backend.acma.gov.au/gmbl/api/Domain

Direct API endpoint — no scraping or browser needed.
Returns JSON list of blocked gambling domains.

Outputs: australia_blacklist.csv (canonical format — timestamp line 1, one domain per line)
"""

import re
import os
import json
import requests
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

API_URL      = "https://backend.acma.gov.au/gmbl/api/Domain"
MIN_EXPECTED = 50

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
    'Referer': 'https://www.acma.gov.au/',
}


def write_canonical_csv(domains, filepath):
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for d in sorted(set(domains)):
            f.write(d.strip() + '\n')
    print(f"💾  Saved {len(domains)} domains → {filepath}  (stamp: {stamp})")


def clean_domain(raw):
    d = raw.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.rstrip('/')


def is_valid_domain(d):
    return bool(d and '.' in d and ' ' not in d and 3 < len(d) < 100)


def fetch_domains():
    print(f"🌐  Calling ACMA API: {API_URL}")
    resp = requests.get(API_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    print(f"    ✅  HTTP {resp.status_code} — {len(resp.content):,} bytes")

    data = resp.json()
    print(f"    📦  Raw response type: {type(data).__name__}")

    # Save raw response for inspection
    with open('debug_acma_api.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print("    💾  Saved debug_acma_api.json")

    domains = set()

    # Walk the JSON structure to find domain strings
    def walk(obj, depth=0):
        if depth > 10:
            return
        if isinstance(obj, str):
            cleaned = clean_domain(obj)
            if is_valid_domain(cleaned):
                domains.add(cleaned)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v, depth + 1)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, depth + 1)

    walk(data)

    # Show structure hint if few domains found
    if len(domains) < MIN_EXPECTED:
        print(f"\n    ⚠️  Only {len(domains)} domains found via walk.")
        print(f"    Response preview (first 500 chars):")
        print(json.dumps(data)[:500])

    return sorted(domains)


def main():
    print("=" * 60)
    print("🇦🇺  AUSTRALIA — ACMA Blocked Gambling Websites (API)")
    print("=" * 60)

    try:
        domains = fetch_domains()
    except Exception as e:
        print(f"❌  Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n📊  Found {len(domains)} unique blocked domains")

    if not domains:
        print("❌  No domains found — check debug_acma_api.json")
        return

    if len(domains) < MIN_EXPECTED:
        print(f"❌  Only {len(domains)} — below minimum of {MIN_EXPECTED}, not writing")
        return

    print(f"\n🔍  First 10 entries:")
    for d in domains[:10]:
        print(f"    {d}")
    if len(domains) > 10:
        print(f"    ... and {len(domains) - 10} more")

    write_canonical_csv(domains, 'australia_blacklist.csv')
    print("✅  Done.")


if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
