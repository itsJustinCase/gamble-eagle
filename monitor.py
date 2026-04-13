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

    # DEBUG: Print keys to see the actual structure in GitHub logs
    print(f"API Response Keys: {list(data.keys())}")

    # Adjusted extraction based on common API patterns
    # If the keys are different, we will see them in the logs
    domains = data.get("domains") or data.get("total_domains") or data.get("count")
    updated = data.get("updated_at") or data.get("last_update") or data.get("date")

    current_stats = {
        "domains": domains,
        "last_updated": updated
    }

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            previous_stats = json.load(f)
    else:
        previous_stats = {}

    if current_stats != previous_stats:
        print(f"CHANGE DETECTED: {current_stats}")
        with open(STATE_FILE, "w") as f:
            json.dump(current_stats, f)
        sys.exit(1) 
    else:
        print("No changes.")
        sys.exit(0)

if __name__ == "__main__":
    monitor()
