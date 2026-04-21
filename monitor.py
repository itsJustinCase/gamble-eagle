import requests
import json
import os
import sys

URL        = "https://monitoring.pc.gov.ua/api/monitor-stats"
STATE_FILE = "last_state.json"

def monitor():
    try:
        response = requests.get(URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Fetch failed: {e}")
        sys.exit(0)

    print(f"API Response Keys: {list(data.keys())}")

    domains = data.get("domains") or data.get("total_domains") or data.get("count")
    updated = data.get("updated_at") or data.get("last_update") or data.get("date")

    current_stats = {"domains": domains, "last_updated": updated}

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            previous_stats = json.load(f)
    else:
        previous_stats = {}

    if current_stats != previous_stats:
        # Print parseable markers for the YAML to extract
        print(f"OLD_DATE={previous_stats.get('last_updated', 'unknown')}")
        print(f"OLD_COUNT={previous_stats.get('domains', 'unknown')}")
        print(f"NEW_DATE={current_stats['last_updated']}")
        print(f"NEW_COUNT={current_stats['domains']}")
        print(f"CHANGE DETECTED: {current_stats}")

        # Write new state so it gets committed by the workflow
        with open(STATE_FILE, "w") as f:
            json.dump(current_stats, f, indent=2)

        sys.exit(1)
    else:
        print("No changes.")
        sys.exit(0)

if __name__ == "__main__":
    monitor()
