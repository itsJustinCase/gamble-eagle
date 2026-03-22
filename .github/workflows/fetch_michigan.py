#!/usr/bin/env python3
"""
US Michigan Licensed Gambling Sites Scraper
============================================
Source: Michigan Gaming Control Board (MGCB)
        https://www.michigan.gov/mgcb/internet-gaming-and-fantasy-contests/
        authorized-online-gaming-and-sports-betting-platform-providers-in-michigan

Extracts licensed platform URLs from the provider table.
Single page — no pagination needed.

URL resolution strategy (applied in order for each anchor):
  1. If the href is a safelinks wrapper (safelinks.protection.outlook.com),
     decode the real URL from the embedded ?url= parameter.
  2. If the anchor text looks like a URL and differs from the decoded href,
     prefer the anchor text (it's always the clean, human-readable URL).
  3. Otherwise use the decoded href.

Post-processing hard filter removes any entry whose domain matches a known
non-operator domain (browser downloads, state government nav links, etc.)
regardless of how it was collected.

Requirements:
    pip install curl-cffi beautifulsoup4
"""

import re
import time
from urllib.parse import urlparse, unquote, parse_qs
from bs4 import BeautifulSoup
from datetime import datetime

try:
    from curl_cffi import requests as cffi_requests
    _USE_CFFI = True
except ImportError:
    import requests as cffi_requests
    _USE_CFFI = False
    print("⚠️  curl_cffi not found — falling back to requests (may get 403).")
    print("    Install with: pip install curl-cffi")

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

SOURCE_URL   = (
    "https://www.michigan.gov/mgcb/internet-gaming-and-fantasy-contests/"
    "authorized-online-gaming-and-sports-betting-platform-providers-in-michigan"
)
MIN_EXPECTED = 5
MAX_RETRIES  = 5
RETRY_DELAY  = 5

# Hard-filter: any collected URL whose domain starts with one of these
# is silently dropped regardless of how it was found on the page.
EXCLUDED_DOMAINS = [
    "google.com",
    "apple.com",
    "microsoft.com",
    "mozilla.org",
    "michigan.gov",
    "mgcb.michigan.gov",
    "safelinks.protection.outlook.com",
    "gcc02.safelinks",
    "nam",           # catches nam02/nam04/nam12.safelinks variants
    # Social media — regulator's own accounts, not operator URLs
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "linkedin.com",
]

# ── Canonical CSV writer ──────────────────────────────────────────────────────

def write_canonical_csv(urls, filepath):
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    stamp = _paris_now().strftime('%Y%m%d %H:%M')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(stamp + '\n')
        for url in unique:
            f.write(url.strip() + '\n')
    print(f"💾  Saved {len(unique)} URLs → {filepath}  (stamp: {stamp})")
    return unique

# ── URL helpers ───────────────────────────────────────────────────────────────

def clean_url(raw):
    """Strip protocol and www. Preserve paths and trailing slashes."""
    url = raw.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url

def decode_safelinks(href):
    """
    If href is a Microsoft safelinks URL, extract and return the real URL.
    Otherwise return href unchanged.
    safelinks format: https://gcc02.safelinks.protection.outlook.com/?url=<encoded>&data=...
    """
    if 'safelinks.protection.outlook.com' not in href:
        return href
    try:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        real = qs.get('url', [None])[0]
        if real:
            return unquote(real)
    except Exception:
        pass
    return href

def looks_like_url(text):
    """Return True if text looks like a bare URL or domain."""
    t = text.strip()
    return bool(
        t.startswith("http://") or
        t.startswith("https://") or
        re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/|$)', t)
    )

def is_excluded(url):
    """Return True if url matches any excluded domain."""
    lower = url.lower()
    return any(ex in lower for ex in EXCLUDED_DOMAINS)

# ── Fetcher with retries ──────────────────────────────────────────────────────

def fetch_page():
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    ↳ Attempt {attempt}/{MAX_RETRIES} "
                  f"({'curl_cffi/Chrome' if _USE_CFFI else 'requests'})...")
            if _USE_CFFI:
                r = cffi_requests.get(SOURCE_URL, impersonate="chrome120", timeout=30)
            else:
                r = cffi_requests.get(SOURCE_URL, timeout=30)
            r.raise_for_status()
            print(f"    ✓ Page loaded (HTTP {r.status_code})")
            return BeautifulSoup(r.content, "html.parser"), None
        except Exception as e:
            last_error = str(e)
            print(f"    ✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"    ⏳ Waiting {RETRY_DELAY}s before retrying...")
                time.sleep(RETRY_DELAY)
    return None, f"Failed after {MAX_RETRIES} attempts — last error: {last_error}"

# ── Extractor ─────────────────────────────────────────────────────────────────

def resolve_anchor(a):
    """
    Given a BeautifulSoup <a> tag, return the best URL string to use.

    Resolution order:
      1. Decode safelinks from href if present → real_href
      2. Check anchor text — if it looks like a URL, use it as candidate_text
      3. If both exist and differ: prefer candidate_text (it's the display URL)
      4. If only one exists, use that
      5. Return None if neither looks usable
    """
    href = a.get("href", "").strip()
    text = a.get_text(strip=True)

    real_href      = decode_safelinks(href) if href else ""
    candidate_text = text if looks_like_url(text) else ""

    if candidate_text and real_href:
        # Both available — prefer text if they refer to different URLs
        # (text is always the human-readable clean URL on this page)
        clean_text = clean_url(candidate_text)
        clean_href = clean_url(real_href)
        if clean_text != clean_href:
            return clean_text   # text wins
        return clean_text       # same either way

    if candidate_text:
        return clean_url(candidate_text)

    if real_href and real_href.startswith("http"):
        return clean_url(real_href)

    return None

def extract_urls(soup):
    """
    Collect operator URLs from the main content area.
    Applies hard exclusion filter as a final safety net.
    """
    urls = []

    # Scope to main content container to avoid nav/footer noise
    content = (
        soup.find("main") or
        soup.find("div", class_=re.compile(
            r'(field.item|cms.content|page.content|wysiwyg|sfContentBlock)', re.I
        )) or
        soup.find("div", id=re.compile(r'(content|main)', re.I)) or
        soup
    )

    if content is soup:
        print("    ⚠️  Could not isolate main content — scanning full page (more noise possible).")

    for a in content.find_all("a", href=True):
        url = resolve_anchor(a)
        if not url:
            continue
        if is_excluded(url):
            print(f"  Skipped (excluded): {url}")
            continue
        if "." not in url:
            continue
        urls.append(url)
        print(f"  Found: {url}")

    return urls

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🇺🇸  US MICHIGAN LICENSED GAMBLING SITES SCRAPER (MGCB)")
    print("=" * 60)
    print(f"🔁  Retry policy: {MAX_RETRIES} attempts × {RETRY_DELAY}s delay")
    if not _USE_CFFI:
        print("⚠️  curl_cffi not installed — run: pip install curl-cffi")
    print()

    print("🔍  Fetching MGCB provider page...")
    soup, error = fetch_page()

    if error:
        print(f"❌  {error}")
        return

    urls = extract_urls(soup)

    if not urls:
        print("❌  No URLs found — check the page structure.")
        return

    unique = write_canonical_csv(urls, 'MI.csv')
    print(f"\n📊  Total unique URLs written: {len(unique)}")

    if len(unique) < MIN_EXPECTED:
        print(f"⚠️  Only {len(unique)} URLs — below expected minimum of {MIN_EXPECTED}.")

    print(f"\n🔍  All URLs:")
    for u in unique:
        print(f"    {u}")

    print("✅  Done.")

if __name__ == "__main__":
    main()
