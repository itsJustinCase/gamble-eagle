#!/usr/bin/env python3
"""
France Licensed Gambling Sites Scraper
=======================================
Source: Autorité Nationale des Jeux (ANJ)
        https://anj.fr/offre-de-jeu-et-marche/operateurs-agrees

Extracts all .fr gambling domains from the ANJ licensed operators page.
Outputs: france.csv (canonical format — timestamp on line 1, one domain per line)
"""

import re
import requests
from bs4 import BeautifulSoup
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

LICENSED_URL = "https://anj.fr/offre-de-jeu-et-marche/operateurs-agrees"
MIN_EXPECTED = 5
EXCLUDED     = {'anj.fr', 'service-public.fr', 'gov.fr', 'legifrance.gouv.fr'}

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


def fetch_licensed():
    print(f"🌐  Fetching ANJ licensed operators page...")
    resp = requests.get(LICENSED_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    print(f"    ✅  HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.content, 'html.parser')
    all_text = soup.get_text()

    raw_domains = re.findall(r'(?<![a-zA-Z0-9])([a-zA-Z0-9][a-zA-Z0-9.-]*\.fr)', all_text)

    domains = set()
    for d in raw_domains:
        cleaned = clean_domain(d)
        if not any(ex in cleaned for ex in EXCLUDED):
            domains.add(cleaned)

    result = sorted(domains)
    print(f"    📊  Found {len(result)} licensed .fr domains")
    return result


def main():
    print("=" * 60)
    print("🇫🇷  FRANCE — Licensed Operators (ANJ)")
    print("=" * 60)

    try:
        licensed = fetch_licensed()
    except Exception as e:
        print(f"❌  Failed to fetch licensed list: {e}")
        return

    if not licensed:
        print("❌  No domains found — not writing france.csv")
        return

    if len(licensed) < MIN_EXPECTED:
        print(f"❌  Only {len(licensed)} domains — below minimum of {MIN_EXPECTED}, not writing")
        return

    write_canonical_csv(licensed, 'france.csv')
    print("✅  Done.")


if __name__ == "__main__":
    main()
