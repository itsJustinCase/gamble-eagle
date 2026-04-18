#!/usr/bin/env python3
"""
Sweden Gambling URLs Extractor - Correct Column
Extracts from the correct Webbadress column
"""

import requests
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


def clean_url(raw):
    """Strip protocol and www. prefix. Trailing slashes preserved."""
    url = raw.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    return url

def download_excel_file():
    """
    Download the Excel file from the export button
    """
    import pandas as pd  # noqa: F401 — imported here to give clear error if missing
    print("🇸🇪 Downloading Swedish gambling sites Excel file...")
    
    # The exact export URL from the network inspection
    export_url = "https://www.spelinspektionen.se/api/export/licenseRegistryExcel"
    
    # Parameters from the network request
    params = {
        'licenseTypes': [21, 20],
        'tab': 2,
        'page': 1
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, */*',
        'Referer': 'https://www.spelinspektionen.se/licens-o-tillstand/licensregister/?licenseTypes=21&licenseTypes=20&tab=2&page=1'
    }
    
    try:
        print(f"🔗 Downloading from: {export_url}")
        response = requests.get(export_url, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'application/vnd.openxmlformats' in content_type or 'excel' in content_type:
                print("✅ Successfully downloaded Excel file")
                print(f"📄 File size: {len(response.content)} bytes")
                return response.content
            else:
                print(f"❌ Unexpected content type: {content_type}")
        else:
            print(f"❌ Download failed: Status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Download error: {e}")
    
    return None

def extract_urls_from_excel(file_content):
    """
    Extract URLs from the correct Webbadress column
    """
    import pandas as pd
    print("📊 Extracting URLs from Excel file...")
    
    # Save the content to a temporary file
    temp_filename = f"swedish_gambling_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    with open(temp_filename, 'wb') as f:
        f.write(file_content)
    
    try:
        # Read the Excel file
        df = pd.read_excel(temp_filename)
        
        print(f"✅ Excel file loaded: {len(df)} rows, {len(df.columns)} columns")
        print(f"📋 All columns: {list(df.columns)}")
        
        # Use the EXACT column name "Webbadress" (last column in your list)
        webaddress_col = "Webbadress"
        
        if webaddress_col not in df.columns:
            print(f"❌ Column '{webaddress_col}' not found!")
            print("Available columns:")
            for i, col in enumerate(df.columns, 1):
                print(f"  {i}. '{col}'")
            return []
        
        print(f"✅ Using column: '{webaddress_col}'")
        
        # Extract ALL values from the Webbadress column
        all_values = []
        empty_count = 0
        non_empty_count = 0
        
        for index, value in enumerate(df[webaddress_col]):
            if pd.isna(value) or value == "" or value is None:
                empty_count += 1
            else:
                non_empty_count += 1
                raw = str(value).strip() if not isinstance(value, str) else value.strip()
                cleaned = clean_url(raw)
                if cleaned:
                    all_values.append(cleaned)
                
                # Show first few non-empty values for debugging
                if non_empty_count <= 5:
                    print(f"  Sample value {non_empty_count}: '{value}' → '{cleaned}'")
        
        print(f"📊 Total rows: {len(df)}")
        print(f"📊 Empty cells in {webaddress_col}: {empty_count}")
        print(f"📊 Non-empty cells in {webaddress_col}: {non_empty_count}")
        print(f"📊 Raw values found: {len(all_values)}")
        
        if non_empty_count == 0:
            print("❌ No data found in Webbadress column!")
            return []
        
        # Remove duplicates while preserving order
        unique_urls = []
        for url in all_values:
            if url not in unique_urls:
                unique_urls.append(url)
        
        print(f"📊 Unique URLs after deduplication: {len(unique_urls)}")
        
        # Show first 20 unique values
        print(f"\n🔍 FIRST 20 UNIQUE VALUES from '{webaddress_col}':")
        for i, url in enumerate(unique_urls[:20], 1):
            print(f"  {i:2d}. {url}")
        
        if len(unique_urls) > 20:
            print(f"  ... and {len(unique_urls) - 20} more")
        
        return unique_urls
        
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        # Clean up temporary file
        import os
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def main():
    print("=" * 60)
    print("🇸🇪 SWEDEN GAMBLING URLS EXTRACTION")
    print("=" * 60)
    
    # pandas is required for Excel handling
    try:
        import pandas as pd  # noqa: F401
    except ImportError:
        print("❌ pandas is required for Excel handling")
        print("💡 Install it with: pip install pandas openpyxl")
        return
    
    start_time = datetime.now()
    
    try:
        # Download the Excel file
        file_content = download_excel_file()
        
        if not file_content:
            print("❌ Could not download Excel file")
            return
        
        # Extract URLs from Excel
        urls = extract_urls_from_excel(file_content)
        
        if not urls:
            print("❌ No URLs extracted from Excel")
            return
        
        print(f"\n📊 EXTRACTION COMPLETED!")
        print(f"🌐 Total unique URLs: {len(urls)}")
        
        # Save canonical CSV
        write_canonical_csv(urls, 'sweden.csv')
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        print(f"\n✅ SUCCESS!")
        print(f"⏱️  Time: {execution_time:.2f} seconds")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
