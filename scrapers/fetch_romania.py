#!/usr/bin/env python3
"""
Romania Licensed Gambling Sites Scraper (ONJN)
===============================================
Source: Oficiul Național pentru Jocuri de Noroc
        https://onjn.gov.ro/licentiati-clasa-i/

Uses curl-cffi to impersonate a real browser and bypass Cloudflare/bot protection
that blocks standard requests and headless Playwright on GitHub Actions runners.
"""

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

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests
    HAS_CURL_CFFI = False
    print("⚠️  curl-cffi not available, falling back to requests (may fail on bot-protected sites)")

from bs4 import BeautifulSoup

URL = "https://onjn.gov.ro/licentiati-clasa-i/"
MIN_EXPECTED = 10

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}


def write_canonical_csv(urls, filepath):
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in urls:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(urls)} URLs → {filepath}  (stamp: {stamp})")


def clean_domain(raw):
    d = raw.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    return d.rstrip('/')


def is_valid_domain(d):
    if not d or len(d) < 4 or '.' not in d:
        return False
    # Must look like a domain, not a sentence or garbage
    if ' ' in d or len(d) > 100:
        return False
    return True


def fetch_page():
    print(f"🌐  Fetching {URL}")
    if HAS_CURL_CFFI:
        # Impersonate Chrome 120 — bypasses most Cloudflare challenges
        resp = cffi_requests.get(
            URL,
            headers=HEADERS,
            impersonate="chrome120",
            timeout=30,
            allow_redirects=True
        )
    else:
        import requests as req
        resp = req.get(URL, headers=HEADERS, timeout=30)

    resp.raise_for_status()
    print(f"    ✅  HTTP {resp.status_code} — {len(resp.content):,} bytes")
    return resp.text


def extract_domains(html):
    soup = BeautifulSoup(html, 'html.parser')

    domains = set()

    # Strategy 1: find all links ending in known Romanian gambling TLDs or .com/.net/.org
    # The ONJN page lists domains as links or plain text in table cells
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        for candidate in [href, text]:
            cleaned = clean_domain(candidate)
            if is_valid_domain(cleaned) and not cleaned.startswith('onjn.gov'):
                domains.add(cleaned)

    # Strategy 2: extract from table cells — ONJN uses a WordPress table plugin
    for td in soup.find_all(['td', 'th']):
        text = td.get_text(strip=True)
        # Match domain patterns: word.tld or word.word.tld
        matches = re.findall(
            r'\b([a-zA-Z0-9][a-zA-Z0-9\-]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)\b',
            text
        )
        for m in matches:
            cleaned = clean_domain(m)
            if is_valid_domain(cleaned) and '.' in cleaned:
                domains.add(cleaned)

    # Filter: keep only plausible gambling domains, exclude nav/UI/system domains
    EXCLUDE = {
        'onjn.gov.ro', 'gov.ro', 'wordpress.com', 'facebook.com', 'twitter.com',
        'youtube.com', 'instagram.com', 'linkedin.com', 'google.com', 'microsoft.com',
        'jquery.com', 'bootstrapcdn.com', 'cloudflare.com', 'gravatar.com',
        'wp.com', 'w3.org', 'schema.org', 'bit.ly', 'goo.gl'
    }

    result = sorted(
        d for d in domains
        if d not in EXCLUDE
        and not any(d.endswith('.' + ex) for ex in EXCLUDE)
        and not d.endswith('.gov.ro')
        and not d.endswith('.gov')
    )

    return result


def main():
    print("=" * 60)
    print("🇷🇴  ROMANIA LICENSED GAMBLING SITES SCRAPER (ONJN)")
    print("=" * 60)

    try:
        html = fetch_page()
    except Exception as e:
        print(f"❌  Failed to fetch page: {e}")
        return

    domains = extract_domains(html)
    print(f"\n📊  Found {len(domains)} candidate domains")

    if len(domains) < MIN_EXPECTED:
        print(f"❌  Below minimum of {MIN_EXPECTED} — page may not have loaded correctly.")
        print("    First 500 chars of HTML:")
        print(html[:500])
        print("\n    Aborting write to protect existing data.")
        return

    print("\n🔍  First 15 domains:")
    for d in domains[:15]:
        print(f"    {d}")
    if len(domains) > 15:
        print(f"    ... and {len(domains) - 15} more")

    write_canonical_csv(domains, 'romania.csv')
    print("✅  Done.")


if __name__ == "__main__":
    main()
