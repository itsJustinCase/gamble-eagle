#!/usr/bin/env python3
"""
Brazil Licensed Gambling Sites Scraper
=======================================
Source: Secretaria de Prêmios e Apostas (SPA) — Ministério da Fazenda
        https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/lista-de-empresas/

Fetches two CSV files published on the SPA page:
  1. Empresas autorizadas (main authorised list)
  2. Empresas por determinação judicial (court-ordered list)

Both CSVs use semicolons as delimiters.
The DOMÍNIOS column contains the licensed domains.
Entries marked "a definir" (to be confirmed) are skipped.

The page is scraped first to find the current CSV URLs — these change
with each update (e.g. planilha-de-autorizacoes-13-03-26.csv).
The script detects them dynamically so it never needs a hardcoded URL.
"""

import re
import csv
import io
import requests
from datetime import datetime
from bs4 import BeautifulSoup

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

INDEX_URL = (
    "https://www.gov.br/fazenda/pt-br/composicao/orgaos/"
    "secretaria-de-premios-e-apostas/lista-de-empresas/"
    "confira-a-lista-de-empresas-autorizadas-a-ofertar-apostas-de-quota-fixa-em-2025"
)

BASE_URL = "https://www.gov.br"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# Minimum expected domains — guards against empty/broken response
MIN_EXPECTED = 50

# ── Canonical CSV writer ──────────────────────────────────────────────────────

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

# ── URL cleaning ──────────────────────────────────────────────────────────────

def clean_domain(raw):
    """Strip protocol, www., and whitespace. Return lowercase domain."""
    d = raw.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    d = d.rstrip('/')
    return d

def is_valid(domain):
    """Filter out empty values, placeholders, and non-domain strings."""
    if not domain:
        return False
    low = domain.lower().strip()
    if low in ('a definir', 'a definir.', '', '-', 'n/a', 'nd'):
        return False
    if '.' not in low:
        return False
    if len(low) < 4:
        return False
    return True

# ── Page scraper — find current CSV URLs ─────────────────────────────────────

def find_csv_urls(session):
    """
    Scrape the SPA index page to find the current CSV download links.
    Returns a list of absolute CSV URLs.
    The page always has two callout paragraphs, each with a CSV link.
    """
    print(f"🌐  Fetching index page to find CSV URLs...")
    r = session.get(INDEX_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, 'html.parser')
    csv_urls = []

    # Look for all links ending in .csv on the page
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.endswith('.csv'):
            # Make absolute if relative
            if href.startswith('http'):
                csv_urls.append(href)
            else:
                csv_urls.append(BASE_URL + href)

    if not csv_urls:
        print("    ⚠️  No CSV links found on page — check page structure.")
    else:
        for u in csv_urls:
            print(f"    📄  Found: {u}")

    return csv_urls

# ── CSV fetcher and domain extractor ─────────────────────────────────────────

def fetch_and_extract(session, csv_url):
    """
    Download a CSV from the SPA site and extract domains from the DOMÍNIOS column.
    Both CSVs use semicolons as delimiters with BOM (utf-8-sig).
    Returns a list of clean domain strings.
    """
    print(f"📥  Downloading {csv_url.split('/')[-1]}...")
    r = session.get(csv_url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    # Detect encoding — gov.br CSVs use UTF-8 with BOM
    content = r.content.decode('utf-8-sig', errors='replace')
    domains = []

    reader = csv.reader(io.StringIO(content), delimiter=';')
    rows = list(reader)

    # Find the header row containing 'DOMÍNIOS' (case-insensitive, strip spaces)
    domain_col = None
    header_row_idx = None
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if 'dom' in cell.lower() and ('nio' in cell.lower() or 'nios' in cell.lower()):
                domain_col = j
                header_row_idx = i
                print(f"    ✅  Found DOMÍNIOS column at index {j} (row {i}): '{cell.strip()}'")
                break
        if domain_col is not None:
            break

    if domain_col is None:
        print("    ❌  Could not find DOMÍNIOS column — check CSV structure.")
        return []

    # Extract domain values from all rows after the header
    found = 0
    skipped_definir = 0
    for row in rows[header_row_idx + 1:]:
        if len(row) <= domain_col:
            continue
        raw = row[domain_col].strip()
        if not raw:
            continue
        # Skip "a definir" entries
        if 'a definir' in raw.lower():
            skipped_definir += 1
            continue
        cleaned = clean_domain(raw)
        if is_valid(cleaned):
            domains.append(cleaned)
            found += 1

    print(f"    📊  Extracted {found} domains"
          + (f" ({skipped_definir} 'a definir' skipped)" if skipped_definir else ""))
    return domains

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇧🇷  BRAZIL LICENSED GAMBLING SITES SCRAPER (SPA)")
    print("=" * 60)

    session = requests.Session()
    all_domains = []

    # Step 1: Find current CSV URLs from the index page
    try:
        csv_urls = find_csv_urls(session)
    except Exception as e:
        print(f"❌  Failed to fetch index page: {e}")
        return

    if not csv_urls:
        print("❌  No CSV URLs found — cannot continue.")
        return

    # Step 2: Download and extract from each CSV
    for url in csv_urls:
        try:
            domains = fetch_and_extract(session, url)
            all_domains.extend(domains)
        except Exception as e:
            print(f"    ❌  Failed to process {url}: {e}")

    # Step 3: Deduplicate, sort
    seen = set()
    unique = []
    for d in all_domains:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    unique.sort()

    print(f"\n📊  Total unique domains: {len(unique)}")

    # Step 4: Guard against empty/broken result
    if len(unique) < MIN_EXPECTED:
        print(f"❌  Only {len(unique)} domains found — below minimum of {MIN_EXPECTED}.")
        print("    Aborting write to protect existing data.")
        return

    # Step 5: Preview
    print(f"\n🔍  First 10 domains:")
    for d in unique[:10]:
        print(f"    {d}")
    if len(unique) > 10:
        print(f"    ... and {len(unique) - 10} more")

    # Step 6: Write canonical CSV
    write_canonical_csv(unique, 'brazil.csv')
    print("✅  Done.")

if __name__ == "__main__":
    main()
