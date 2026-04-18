#!/usr/bin/env python3
"""
Portugal Licensed Gambling Sites Scraper
=========================================
Source: Serviço de Regulação e Inspeção de Jogos (SRIJ)
        https://www.srij.turismodeportugal.pt/pt/jogos-e-apostas-online/entidades-licenciadas

The SRIJ site uses a certificate chain that Python's ssl cannot verify
(intermediate CA not in the default bundle). We disable verification
with verify=False — this is safe here since we are only reading public
regulatory data, not submitting credentials.

The page lists licensed operators with Brand (Marca), URL (Website),
and licensed entity (Entidade exploradora).
We extract the Website field for each entry and strip www. / protocol.

Requirements:
    pip install requests beautifulsoup4 urllib3
"""

import re
import time
import warnings
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime

# Suppress the InsecureRequestWarning that comes with verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

SOURCE_URL   = "https://www.srij.turismodeportugal.pt/pt/jogos-e-apostas-online/entidades-licenciadas"
MIN_EXPECTED = 5
MAX_RETRIES  = 5
RETRY_DELAY  = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
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
    url = raw.strip().lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip('/')
    return url

def looks_like_domain(text):
    t = text.strip()
    return bool(re.match(
        r'^(https?://)?(www\.)?[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/\S*)?$', t
    )) and ' ' not in t and len(t) < 100

# ── Fetcher with retries ──────────────────────────────────────────────────────

def fetch_page():
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES}...")
            # verify=False: SRIJ's cert chain is missing an intermediate CA
            # that isn't in Python's default bundle.
            r = requests.get(SOURCE_URL, headers=HEADERS, timeout=20, verify=False)
            r.raise_for_status()
            print(f"    ✓ Loaded (HTTP {r.status_code})")
            return BeautifulSoup(r.content, "html.parser"), None
        except Exception as e:
            last_error = str(e)
            print(f"    ✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ Waiting {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
    return None, f"Failed after {MAX_RETRIES} attempts — {last_error}"

# ── Extractor ─────────────────────────────────────────────────────────────────

def extract_urls(soup):
    """
    The SRIJ page lists each operator in a structured block with labelled
    fields. We look for the 'Website' label and grab the value next to it.

    Strategies applied in order:
      1. Definition lists: <dt>Website</dt><dd>value</dd>
      2. Table rows where first cell contains 'Website'
      3. Elements whose text contains 'Website:' with inline value
      4. Fallback: all anchors whose text looks like a .pt domain
    """
    urls = []
    seen = set()

    def add(raw):
        if not raw:
            return
        cleaned = clean_url(raw)
        if (cleaned and "." in cleaned and cleaned not in seen
                and re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', cleaned)):
            seen.add(cleaned)
            urls.append(cleaned)
            print(f"  Found: {cleaned}")

    # ── Strategy 1: dl/dt/dd ──────────────────────────────────────────────
    for dt in soup.find_all("dt"):
        if "website" in dt.get_text(strip=True).lower():
            dd = dt.find_next_sibling("dd")
            if dd:
                a = dd.find("a", href=True)
                add(a["href"] if a else dd.get_text(strip=True))

    # ── Strategy 2: table rows ────────────────────────────────────────────
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 2 and "website" in cells[0].get_text(strip=True).lower():
            a = cells[1].find("a", href=True)
            add(a["href"] if a else cells[1].get_text(strip=True))

    # ── Strategy 3: inline 'Website:' label ──────────────────────────────
    for elem in soup.find_all(string=re.compile(r'Website\s*:', re.IGNORECASE)):
        parent = elem.parent
        if not parent:
            continue
        nxt = parent.find_next_sibling()
        if nxt:
            a = nxt.find("a", href=True) if hasattr(nxt, 'find') else None
            if a:
                add(a["href"])
            else:
                txt = nxt.get_text(strip=True) if hasattr(nxt, 'get_text') else ""
                if looks_like_domain(txt):
                    add(txt)
        # Also check for URL inline after the colon
        full = parent.get_text(strip=True) if hasattr(parent, 'get_text') else ""
        m = re.search(r'Website\s*:\s*(\S+)', full, re.IGNORECASE)
        if m and looks_like_domain(m.group(1)):
            add(m.group(1))

    # ── Strategy 4: anchors whose text is a .pt domain ───────────────────
    if not urls:
        print("    ℹ️  Label strategies found nothing — scanning all .pt anchors...")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"].strip()
            candidate = text if looks_like_domain(text) else href
            if looks_like_domain(candidate):
                cleaned = clean_url(candidate)
                if cleaned.endswith(".pt") or any(
                    cleaned.endswith(t) for t in [".bet", ".casino", ".poker"]
                ):
                    add(cleaned)

    return urls

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇵🇹  PORTUGAL LICENSED GAMBLING SITES SCRAPER (SRIJ)")
    print("=" * 60)
    print(f"🔁  Retry policy: {MAX_RETRIES} attempts × {RETRY_DELAY}s delay")
    print("ℹ️   SSL verification disabled (SRIJ uses incomplete cert chain)\n")

    print("🔍  Fetching SRIJ licensed operators page...")
    soup, error = fetch_page()
    if error:
        print(f"❌  {error}")
        return

    urls = extract_urls(soup)

    if not urls:
        print("❌  No URLs found — the page structure may have changed.")
        return

    unique = write_canonical_csv(urls, 'portugal.csv')
    print(f"\n📊  Total unique URLs written: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"⚠️  Only {len(unique)} — below expected minimum of {MIN_EXPECTED}.")

    print(f"\n🔍  All URLs:")
    for u in unique:
        print(f"    {u}")

    print("\n✅  Done.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
