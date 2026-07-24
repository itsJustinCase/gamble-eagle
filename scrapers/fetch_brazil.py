#!/usr/bin/env python3
"""
Brazil Licensed Gambling Sites Scraper
=======================================
Source: Secretaria de Prêmios e Apostas (SPA) — Ministério da Fazenda
        https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/lista-de-empresas/
"""

import os
import re
import csv
import io
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import openpyxl

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

MIN_EXPECTED = 20

# ── Canonical CSV writer ──────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in urls:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(urls)} URLs → {filepath}  (stamp: {stamp})")

# ── URL cleaning ──────────────────────────────────────────────────────────────

def clean_domain(raw):
    d = raw.strip().lower()
    d = re.sub(r'^https?://', '', d)
    d = re.sub(r'^www\.', '', d)
    d = d.rstrip('/')
    return d

def is_valid(domain):
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

# ── Page Scraper — Dynamic Link Finder ────────────────────────────────────────

def find_target_file_urls(session):
    print("🌐  Fetching index page to find target file URLs...")
    r = session.get(INDEX_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, 'html.parser')
    file_urls = []

    # Dynamic regex matching for target authorization spreadsheet and judicial processes
    patterns = [
        re.compile(r'planilha.*autoriza', re.IGNORECASE),
        re.compile(r'processos.*judiciais', re.IGNORECASE)
    ]

    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text()
        
        if any(p.search(href) or p.search(text) for p in patterns):
            target_url = href if href.startswith('http') else BASE_URL + href
            if target_url not in file_urls:
                file_urls.append(target_url)

    for u in file_urls:
        print(f"    📄  Found: {u}")

    return file_urls

# ── Parsers ───────────────────────────────────────────────────────────────────

def extract_from_excel(content):
    domains = []
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    
    for sheetname in wb.sheetnames:
        sheet = wb[sheetname]
        domain_col = None
        header_row_idx = None

        rows = list(sheet.iter_rows(values_only=True))
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                if cell and isinstance(cell, str):
                    if 'dom' in cell.lower() and ('nio' in cell.lower() or 'nios' in cell.lower()):
                        domain_col = j
                        header_row_idx = i
                        break
            if domain_col is not None:
                break

        if domain_col is None:
            continue

        for row in rows[header_row_idx + 1:]:
            if len(row) <= domain_col or row[domain_col] is None:
                continue
            raw = str(row[domain_col]).strip()
            if 'a definir' in raw.lower():
                continue
            cleaned = clean_domain(raw)
            if is_valid(cleaned):
                domains.append(cleaned)

    return domains

def extract_from_csv(content_bytes):
    content = content_bytes.decode('utf-8-sig', errors='replace')
    domains = []
    reader = csv.reader(io.StringIO(content), delimiter=';')
    rows = list(reader)

    domain_col = None
    header_row_idx = None
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if 'dom' in cell.lower() and ('nio' in cell.lower() or 'nios' in cell.lower()):
                domain_col = j
                header_row_idx = i
                break
        if domain_col is not None:
            break

    if domain_col is None:
        return []

    for row in rows[header_row_idx + 1:]:
        if len(row) <= domain_col:
            continue
        raw = row[domain_col].strip()
        if not raw or 'a definir' in raw.lower():
            continue
        cleaned = clean_domain(raw)
        if is_valid(cleaned):
            domains.append(cleaned)

    return domains

def fetch_and_extract(session, url):
    print(f"📥  Downloading {url.split('/')[-1]}...")
    r = session.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    if url.lower().endswith('.xlsx'):
        domains = extract_from_excel(r.content)
    else:
        domains = extract_from_csv(r.content)

    print(f"    📊  Extracted {len(domains)} domains")
    return domains

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇧🇷  BRAZIL LICENSED GAMBLING SITES SCRAPER (SPA)")
    print("=" * 60)

    session = requests.Session()
    all_domains = []

    try:
        urls = find_target_file_urls(session)
    except Exception as e:
        print(f"❌  Failed to fetch index page: {e}")
        return

    if not urls:
        print("❌  No target file URLs found on page.")
        return

    for url in urls:
        try:
            domains = fetch_and_extract(session, url)
            all_domains.extend(domains)
        except Exception as e:
            print(f"    ❌  Failed to process {url}: {e}")

    seen = set()
    unique = []
    for d in all_domains:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    unique.sort()

    print(f"\n📊  Total unique domains: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"❌  Only {len(unique)} domains found — below minimum threshold ({MIN_EXPECTED}).")
        return

    print(f"\n🔍  First 10 domains:")
    for d in unique[:10]:
        print(f"    {d}")
    if len(unique) > 10:
        print(f"    ... and {len(unique) - 10} more")

    write_canonical_csv(unique, 'brazil.csv')
    print("✅  Done.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
