import requests
import json
import os
import datetime
import config

def scrape_to_file(route_id):
    # Ensure a folder exists for these captures
    folder = os.path.join(config.PROJECT_ROOT_PATH, "scrapes")
    if not os.path.exists(folder): os.makedirs(folder)

    url = f"https://online.ammanbus.jo/api/v1/bus/GetBusLocations?routeId={route_id}"
    timestamp = datetime.datetime.now().strftime("%H-%M-%S")
    filename = f"route_{route_id}_{timestamp}.json"
    filepath = os.path.join(folder, filename)

    print(f"[{timestamp}] Scraping Route {route_id}...")
    
    try:
        response = requests.get(url, headers=config.HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            print(f"✅ Saved to: {filename}")
            return data
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    return None

if __name__ == "__main__":
    # Example: Scrape the three main routes once
    for rid in ["98", "99", "100"]:
        scrape_to_file(rid)