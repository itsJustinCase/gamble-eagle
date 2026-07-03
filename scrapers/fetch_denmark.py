#!/usr/bin/env python3
"""
Danish Gambling Authority - Domain Extractor
Extracts domains from the Domains column in the table
All 7 license filters selected
UTF-8 with BOM for proper encoding
Outputs to denmark.csv for GitHub workflow
"""

import sys
import time
import csv
import re
import traceback
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Please install: pip install selenium webdriver-manager")
    print("\nPress ENTER to close...")
    input()
    sys.exit(1)


# ============================================================
# ALL 7 LICENSE TYPES
# ============================================================
TARGET_FILTERS = [
    "Betting",
    "Class lottery",
    "Lottery - monopoly",
    "Online casino",
    "Poker",
    "Revenue-restricted betting",
    "Revenue-restricted online casino",
]


def setup_driver():
    """Setup Chrome driver"""
    print("   Starting Chrome...")
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("   ✅ Chrome started")
        return driver
    except Exception as e:
        print(f"   ❌ Failed to start Chrome: {e}")
        raise


def accept_cookies(driver):
    """Accept cookies to dismiss the banner"""
    try:
        print("   Accepting cookies...")
        accept_xpaths = [
            "//button[contains(text(), 'ACCEPT')]",
            "//button[@aria-label='Accept']",
            "//button[contains(@class, 'coi-banner__accept')]",
            "//button[contains(text(), 'Accept')]",
        ]
        
        for xpath in accept_xpaths:
            try:
                accept_btn = driver.find_element(By.XPATH, xpath)
                if accept_btn.is_displayed() and accept_btn.is_enabled():
                    driver.execute_script("arguments[0].click();", accept_btn)
                    print("   ✅ Cookies accepted")
                    time.sleep(2)
                    return True
            except:
                continue
    except Exception as e:
        print(f"   ⚠️  Could not accept cookies: {e}")
    
    return False


def apply_filters(driver):
    """
    Apply all 7 license type filters
    """
    print("   Applying all 7 license filters...")
    
    try:
        time.sleep(2)
        
        # Try to find filter checkboxes
        checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
        
        if checkboxes:
            print(f"   Found {len(checkboxes)} checkboxes")
            
            for checkbox in checkboxes:
                label_text = ""
                try:
                    label = checkbox.find_element(By.XPATH, "./following-sibling::label | ./parent::*/label")
                    label_text = label.text.strip()
                except:
                    label_text = checkbox.get_attribute("value") or ""
                
                if not label_text:
                    continue
                
                should_enable = False
                for target in TARGET_FILTERS:
                    if target.lower() in label_text.lower():
                        should_enable = True
                        break
                
                is_checked = checkbox.is_selected()
                
                if should_enable and not is_checked:
                    print(f"      ✅ Enabling: {label_text}")
                    driver.execute_script("arguments[0].click();", checkbox)
                    time.sleep(0.5)
                elif not should_enable and is_checked:
                    print(f"      ⬜ Disabling: {label_text}")
                    driver.execute_script("arguments[0].click();", checkbox)
                    time.sleep(0.5)
                else:
                    if should_enable:
                        print(f"      ✓ Already enabled: {label_text}")
            
            time.sleep(2)
            return
        
        # If no checkboxes, look for filter pills
        print("   No checkboxes found, looking for filter pills...")
        
        for target in TARGET_FILTERS:
            try:
                elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{target}')]")
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        text = el.text.strip()
                        is_active = '×' in text or 'active' in (el.get_attribute('class') or '')
                        
                        if not is_active:
                            print(f"      ✅ Clicking: {target}")
                            driver.execute_script("arguments[0].click();", el)
                            time.sleep(0.5)
                        else:
                            print(f"      ✓ Already active: {target}")
            except:
                continue
        
        time.sleep(2)
        
    except Exception as e:
        print(f"   ⚠️  Error applying filters: {e}")


def scroll_page(driver):
    """Scroll the page to trigger lazy loading"""
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)


def get_total_pages(driver):
    """Get total pages from pagination text"""
    try:
        page_info = driver.find_element(By.XPATH, "//*[contains(text(), 'Page') and contains(text(), 'out of')]")
        page_text = page_info.text
        match = re.search(r'Page \d+ out of (\d+) pages', page_text, re.IGNORECASE)
        if match:
            total = int(match.group(1))
            print(f"   📊 Found pagination: {page_text}")
            return total
    except:
        pass
    
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r'Page \d+ out of (\d+) pages', body_text, re.IGNORECASE)
        if match:
            total = int(match.group(1))
            print(f"   📊 Found pagination: {match.group(0)}")
            return total
    except:
        pass
    
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r'(\d+)\s*[Tt]otal\s*[Rr]esults', body_text)
        if match:
            total_results = int(match.group(1))
            total_pages = (total_results + 19) // 20
            print(f"   📊 Found {total_results} total results, {total_pages} pages")
            return total_pages
    except:
        pass
    
    print("   ⚠️  Could not detect total pages, assuming 1")
    return 1


def get_current_page(driver):
    """Get current page number"""
    try:
        page_info = driver.find_element(By.XPATH, "//*[contains(text(), 'Page') and contains(text(), 'out of')]")
        page_text = page_info.text
        match = re.search(r'Page (\d+) out of \d+ pages', page_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    except:
        pass
    
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r'Page (\d+) out of \d+ pages', body_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    except:
        pass
    
    return 1


def extract_domains_from_table(driver):
    """Extract domains from the Domains column in the table"""
    domains = []
    
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        
        scroll_page(driver)
        time.sleep(2)
        
        tables = driver.find_elements(By.TAG_NAME, "table")
        
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            if len(rows) < 2:
                continue
            
            domain_col_index = -1
            header_cells = rows[0].find_elements(By.TAG_NAME, "th")
            
            for i, cell in enumerate(header_cells):
                text = cell.text.strip().lower()
                if 'domain' in text:
                    domain_col_index = i
                    break
            
            if domain_col_index != -1:
                for row in rows[1:]:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) > domain_col_index:
                        cell_text = cells[domain_col_index].text.strip()
                        if cell_text:
                            parts = re.split(r'[\s,;]+', cell_text)
                            for d in parts:
                                d = d.strip()
                                if d and d not in domains:
                                    domains.append(d)
        
    except TimeoutException:
        print("   ⚠️  Timeout waiting for table")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    return domains


def go_to_next_page(driver):
    """Navigate to the next page"""
    xpaths = [
        "//button[@aria-label='Next page']",
        "//button[contains(@aria-label, 'Next')]",
        "//button[contains(@class, 'pagination-btn')]",
        "//a[@aria-label='Next page']",
        "//a[contains(@class, 'pagination-btn')]",
        "//a[contains(@class, 'next')]",
        "//li[contains(@class, 'next')]/a",
        "//li[contains(@class, 'next')]/button",
    ]
    
    for xpath in xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed() and el.is_enabled():
                    print("   Clicking Next button...")
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(3)
                    return True
        except:
            continue
    
    return False


def scrape_all_pages():
    """Scrape all pages"""
    driver = None
    all_domains = []
    
    try:
        driver = setup_driver()
        
        url = "https://spillemyndigheden.dk/en-us/licensed-gambling-operators"
        
        print("=" * 70)
        print("DANISH GAMBLING AUTHORITY - DOMAIN EXTRACTOR")
        print("=" * 70)
        print()
        
        print("📋 License filters to apply:")
        for f in TARGET_FILTERS:
            print(f"   ✅ {f}")
        print()
        
        print(f"📄 Loading: {url}")
        driver.get(url)
        
        print("⏳ Waiting for page to render...")
        time.sleep(3)
        
        accept_cookies(driver)
        time.sleep(3)
        
        apply_filters(driver)
        
        scroll_page(driver)
        time.sleep(2)
        
        total_pages = get_total_pages(driver)
        print(f"\n📊 Total pages detected: {total_pages}")
        print()
        
        current_page = get_current_page(driver)
        print(f"   Starting on page {current_page}")
        
        page_num = current_page
        
        while page_num <= total_pages:
            if page_num > 1:
                print(f"\n   Going to page {page_num}...")
                if not go_to_next_page(driver):
                    print(f"   ⚠️  Could not go to page {page_num}")
                    break
                time.sleep(2)
            
            print(f"\n📄 Page {page_num}...")
            
            domains = extract_domains_from_table(driver)
            
            filtered_domains = []
            for d in domains:
                clean_d = re.sub(r'^www\.', '', d)
                if clean_d not in filtered_domains:
                    filtered_domains.append(clean_d)
            
            if filtered_domains:
                print(f"   ✅ Found {len(filtered_domains)} domains")
                for d in filtered_domains[:5]:
                    print(f"      - {d}")
                if len(filtered_domains) > 5:
                    print(f"      ... and {len(filtered_domains) - 5} more")
                
                for d in filtered_domains:
                    if d not in all_domains:
                        all_domains.append(d)
            else:
                print(f"   ⚠️  No domains found on page {page_num}")
            
            print(f"   Total so far: {len(all_domains)}")
            
            page_num += 1
        
        print(f"\n🏁 Done. Total unique domains: {len(all_domains)}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
    
    finally:
        if driver:
            driver.quit()
    
    return all_domains


def save_to_csv(domains):
    """Save domains to denmark.csv with UTF-8 BOM for proper encoding"""
    if not domains:
        print("\n❌ No domains to save")
        return False
    
    domains_sorted = sorted(domains, key=lambda x: x.lower())
    
    # Fixed filename for GitHub workflow
    filename = "denmark.csv"
    
    # Use utf-8-sig to add BOM (Byte Order Mark)
    # This ensures Excel and other programs recognize it as UTF-8
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        # Write timestamp as first line
        timestamp = datetime.now().strftime("%Y%m%d %H:%M")
        writer.writerow([timestamp])
        for domain in domains_sorted:
            writer.writerow([domain])
    
    print("\n" + "=" * 70)
    print("✅ RESULTS")
    print("=" * 70)
    print(f"📁 File saved: {filename}")
    print(f"📅 Timestamp: {timestamp}")
    print(f"🌐 Total domains: {len(domains_sorted)}")
    
    return True


def main():
    """Main execution"""
    print("=" * 70)
    print("LICENSED GAMBLING OPERATORS - DOMAIN EXTRACTOR")
    print("=" * 70)
    print()
    
    try:
        domains = scrape_all_pages()
        
        if domains:
            save_to_csv(domains)
        else:
            print("\n❌ No domains found.")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("🔄 Press ENTER to close this window...")
    input()


if __name__ == "__main__":
    main()
