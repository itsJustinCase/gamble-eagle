import requests
import json
import os
import sys

URL = "https://monitoring.pc.gov.ua/api/monitor-stats"
STATE_FILE = "last_state.json"

def monitor():
    try:
        response = requests.get(URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Fetch failed: {e}")
        sys.exit(0)

    # Targeted parameters
    current_stats = {
        "domains": data.get("domains_count"),
        "last_updated": data.get("last_updated")
    }

    # Load previous state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            previous_stats = json.load(f)
    else:
        previous_stats = {}

    # Check for changes
    if current_stats != previous_stats:
        print(f"CHANGE DETECTED: {current_stats}")
        with open(STATE_FILE, "w") as f:
            json.dump(current_stats, f)
        # Exit with 1 to signal the workflow that a change occurred
        sys.exit(1) 
    else:
        print("No changes detected.")
        sys.exit(0)

if __name__ == "__main__":
    monitor()
