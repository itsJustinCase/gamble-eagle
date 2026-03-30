#!/usr/bin/env python3
"""
France ANJ Blacklist Scraper
=============================
Source: Autorité Nationale des Jeux (ANJ) — Liste noire
        https://ressources.anj.fr/blocage_sites_illegaux/blocage_sites_illegaux.csv

The ANJ publishes and maintains a CSV of formally banned sites at a stable URL.
Format: SITE;URL;DATE DE LA DECISION
Example row: RICHPRIZE;www.richprize.com;13/06/2022

We extract column 2 (URL), strip www., deduplicate (both www. and bare domain
are often listed as separate rows for the same site).

Outputs: france_blacklist.csv (canonical format — timestamp on line 1, one domain per line)
"""

import re
import csv
import io
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

BLACKLIST_URL = "https://ressources.anj.fr/blocage_sites_illegaux/blocage_sites_illegaux.csv"
MIN_EXPECTED  = 10

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    )
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


def fetch_blacklist():
    print(f"🌐  Downloading ANJ blacklist CSV...")
    resp = requests.get(BLACKLIST_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    print(f"    ✅  HTTP {resp.status_code} — {len(resp.content):,} bytes")

    # ANJ CSV uses UTF-8 with BOM, semicolon delimiter
    content = resp.content.decode('utf-8-sig', errors='replace')
    reader = csv.reader(io.StringIO(content), delimiter=';')

    domains = set()
    skipped = 0
    for row in reader:
        if len(row) < 2:
            continue
        raw_url = row[1].strip()
        # Skip header row
        if raw_url.lower() == 'url' or not raw_url:
            continue
        cleaned = clean_domain(raw_url)
        # Basic validity: must have a dot, no spaces, reasonable length
        if cleaned and '.' in cleaned and ' ' not in cleaned and len(cleaned) > 3:
            domains.add(cleaned)
        else:
            skipped += 1

    result = sorted(domains)
    print(f"    📊  {len(result)} unique blacklisted domains ({skipped} invalid rows skipped)")
    return result


def main():
    print("=" * 60)
    print("🇫🇷  FRANCE — ANJ Blacklist (Liste Noire)")
    print("=" * 60)

    try:
        blacklist = fetch_blacklist()
    except Exception as e:
        print(f"❌  Failed to fetch blacklist: {e}")
        return

    if not blacklist:
        print("❌  No domains found — not writing france_blacklist.csv")
        return

    if len(blacklist) < MIN_EXPECTED:
        print(f"❌  Only {len(blacklist)} domains — below minimum of {MIN_EXPECTED}, not writing")
        return

    print(f"\n🔍  First 10 entries:")
    for d in blacklist[:10]:
        print(f"    {d}")
    if len(blacklist) > 10:
        print(f"    ... and {len(blacklist) - 10} more")

    write_canonical_csv(blacklist, 'france_blacklist.csv')
    print("✅  Done.")


if __name__ == "__main__":
    main()
