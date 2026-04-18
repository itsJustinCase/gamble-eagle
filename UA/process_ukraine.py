import csv
import os
import re
import sys
import glob
from datetime import datetime, timezone, timedelta

# Paths relative to this script
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
# Outputs go to the parent directory (repo root)
OUTPUT_LICENSED  = os.path.join(SCRIPT_DIR, "..", "ukraine.csv")
OUTPUT_BLACKLIST = os.path.join(SCRIPT_DIR, "..", "ukraine_blacklist.csv")

STATUS_LICENSED    = "легальний"
STATUS_BLACKLISTED = "заблокований"

def paris_timestamp():
    paris = timezone(timedelta(hours=2))
    return datetime.now(paris).strftime("%Y%m%d %H:%M")

def clean_domain(raw):
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.rstrip("/")

def write_csv(filepath, domains):
    ts = paris_timestamp()
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(ts + "\n")
        for d in sorted(domains):
            f.write(d + "\n")
    print(f"  Generated {len(domains)} domains -> {os.path.basename(filepath)}")

def main():
    # Look for any file starting with 'full_database' and ending in '.csv'
    search_pattern = os.path.join(SCRIPT_DIR, "full_database*.csv")
    files = glob.glob(search_pattern)

    if not files:
        print(f"Error: No file matching 'full_database*.csv' found in {SCRIPT_DIR}")
        sys.exit(1)
    
    # Use the most recent one if multiple exist
    input_file = max(files, key=os.path.getctime)
    print(f"Processing: {os.path.basename(input_file)}")

    licensed = set()
    blacklisted = set()

    with open(input_file, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0 or not row or not row[0].strip():
                continue
            
            domain = clean_domain(row[0])
            status = row[2].strip().lower() if len(row) > 2 else ""
            
            if status == STATUS_LICENSED:
                licensed.add(domain)
            elif status == STATUS_BLACKLISTED:
                blacklisted.add(domain)

    write_csv(OUTPUT_LICENSED, licensed)
    write_csv(OUTPUT_BLACKLIST, blacklisted)
    print("Update successful.")

if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
