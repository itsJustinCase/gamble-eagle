# process_ukraine.py
# Runs inside GitHub Actions from the UA/ folder.
# Searches for full_database*.csv, processes it, and writes outputs to repo root (../).
# Includes failsafe: exits with code 1 if either list would be empty,
# so the workflow can catch it and send an alert.

import csv
import os
import re
import sys
import glob
from datetime import datetime, timezone, timedelta

SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
OUTPUT_LICENSED  = os.path.join(SCRIPT_DIR, "..", "ukraine.csv")
OUTPUT_BLACKLIST = os.path.join(SCRIPT_DIR, "..", "ukraine_blacklist.csv")

STATUS_LICENSED    = "легальний"
STATUS_BLACKLISTED = "заблокований"

MIN_LICENSED    = 5    # Minimum expected — alert if below this
MIN_BLACKLISTED = 100  # Minimum expected — alert if below this


def paris_timestamp():
    paris = timezone(timedelta(hours=2))
    return datetime.now(paris).strftime("%Y%m%d %H:%M")


def clean_domain(raw):
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.rstrip("/")


def get_status(row):
    """Try column 1 first (new format), fall back to column 2 (old format).
    Case-insensitive — works regardless of capitalisation."""
    for col in [1, 2]:
        if len(row) > col:
            s = row[col].strip().lower()
            if s in (STATUS_LICENSED, STATUS_BLACKLISTED):
                return s
    return ""


def write_csv(filepath, domains):
    ts = paris_timestamp()
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(ts + "\n")
        for d in sorted(domains):
            f.write(d + "\n")
    print(f"  Generated {len(domains)} domains → {os.path.basename(filepath)}")


def main():
    # Find full_database*.csv in the script folder
    files = glob.glob(os.path.join(SCRIPT_DIR, "full_database*.csv"))
    if not files:
        print("ERROR: No file matching 'full_database*.csv' found.")
        sys.exit(1)

    input_file = max(files, key=os.path.getctime)
    print(f"Processing: {os.path.basename(input_file)}")

    licensed    = set()
    blacklisted = set()
    skipped     = 0

    with open(input_file, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:
                print(f"  Header: {row}")
                continue
            if not row or not row[0].strip():
                continue
            domain = clean_domain(row[0])
            if not domain:
                continue
            status = get_status(row)
            if status == STATUS_LICENSED:
                licensed.add(domain)
            elif status == STATUS_BLACKLISTED:
                blacklisted.add(domain)
            else:
                skipped += 1

    print(f"\n  Results:")
    print(f"    Licensed   : {len(licensed)}")
    print(f"    Blacklisted: {len(blacklisted)}")
    print(f"    Skipped    : {skipped}")

    # ── Failsafe ──────────────────────────────────────────────────────────────
    errors = []

    if len(licensed) == 0:
        errors.append("FAILSAFE: 0 licensed domains found — refusing to overwrite ukraine.csv")
    elif len(licensed) < MIN_LICENSED:
        errors.append(f"FAILSAFE: Only {len(licensed)} licensed domains found (minimum: {MIN_LICENSED})")

    if len(blacklisted) == 0:
        errors.append("FAILSAFE: 0 blacklisted domains found — refusing to overwrite ukraine_blacklist.csv")
    elif len(blacklisted) < MIN_BLACKLISTED:
        errors.append(f"FAILSAFE: Only {len(blacklisted)} blacklisted domains found (minimum: {MIN_BLACKLISTED})")

    if errors:
        for e in errors:
            print(f"\n  ❌ {e}")
        print("\n  Output files NOT written. Workflow should send an alert.")
        sys.exit(1)  # Non-zero exit triggers workflow failure → email alert

    # ── Write outputs ─────────────────────────────────────────────────────────
    write_csv(OUTPUT_LICENSED,  licensed)
    write_csv(OUTPUT_BLACKLIST, blacklisted)
    print("\nUpdate successful.")


if __name__ == "__main__":
    main()
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
