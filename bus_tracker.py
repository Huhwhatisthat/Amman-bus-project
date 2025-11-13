import requests
import json
import time
import random
import datetime
import pandas as pd
import os
import firebase_admin
from firebase_admin import credentials, firestore
from haversine import haversine, Unit
import subprocess

# --- SCRIPT CONFIGURATION v4.4 ---

# --- 1. Your Personal Settings ---
USER_LOCATION = (32.008, 35.521) # Your updated location
AVG_WALK_SPEED_MPS = 1.3 
AVG_BUS_SPEED_MPS = 8.3  

# --- 2. MVP Settings ---
STOPS_TO_MONITOR = [
    {
        "name": "J.U Hospital (To Museum)",
        "stopId": "10619",
        "direction": 0
    },
    {
        "name": "J.U Hospital (To Swaileh)",
        "stopId": "10620", 
        "direction": 1
    }
]

# --- 3. File Paths & Keys ---
SERVICE_KEY_PATH = r"D:\beaning\bean\serviceAccountKey.json"

### <<< FIX 1: CLEANED UP PATHS BASED ON YOUR SCREENSHOT ---
# This is your main project folder
PROJECT_ROOT_PATH = r"C:\Users\user\Desktop\Amman-bus-project" 

# We will create and use a 'data' folder *inside* your project
HISTORICAL_DATA_PATH = os.path.join(PROJECT_ROOT_PATH, "data")
# This is the 'public' folder *inside* your project
HOSTING_PUBLIC_PATH = os.path.join(PROJECT_ROOT_PATH, "public") 
### --- END OF FIX 1 ---

# --- 4. API & Schedule Settings ---
API_URLS = {
    0: "https://mobile.ammanbus.jo/rl1//web/pathInfo?region=116&lang=en&authType=4&direction=0&displayRouteCode=99&resultType=111111",
    1: "https://mobile.ammanbus.jo/rl1//web/pathInfo?region=116&lang=en&authType=4&direction=1&displayRouteCode=99&resultType=111111"
}
ACTIVE_HOUR_START = 6
ACTIVE_HOUR_END = 0 

# --- 5. n8n (Commented Out) ---
# N8N_FAILURE_URL = "YOUR_FAILURE_URL_HERE"
# N8N_STATUS_URL = "YOUR_STATUS_URL_HERE"

# --- "Morale" Settings ---
GERMAN_QUOTES = [
    ("Wo ein Wille ist, da ist auch ein Weg.", "Where there's a will, there's a way. - German Proverb"),
    ("Ohne Fleiß kein Preis.", "No pain, no gain. - German Proverb")
]
MORALE_PING_TARGETS = [100, 500, 1000, 2500, 5000, 10000] 

# --- Firebase Setup ---
try:
    cred = credentials.Certificate(SERVICE_KEY_PATH)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Successfully connected to Firebase!")
except FileNotFoundError:
    print(f"❌ ERROR: 'serviceAccountKey.json' not found at {SERVICE_KEY_PATH}")
    exit()

# --- HEADERS ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'Referer': 'https://online.ammanbus.jo/',
    'Origin': 'https://online.ammanbus.jo'
}

# ---------------------------------------------
# --- 🚌 BUS AUNTY "MAGIC" LOGIC 🚌 ---
# ---------------------------------------------

def get_static_data_from_firebase(direction):
    """Fetches the static route path and stop list from Firebase."""
    try:
        doc_ref = db.collection("static_route_data").document(f"route_99_dir_{direction}")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            print(f"  > WARNING: No static data found for direction {direction}. Run data collector.")
            return None
    except Exception as e:
        print(f"  > Error getting static data: {e}")
        return None

def get_live_data_from_firebase(direction):
    """Fetches the live bus list from Firebase."""
    try:
        doc_ref = db.collection("live_data").document(f"route99_dir_{direction}")
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('buses', [])
        else:
            print(f"  > WARNING: No live data found for direction {direction}.")
            return []
    except Exception as e:
        print(f"  > Error getting live data: {e}")
        return []

def find_closest_point_on_path(bus_coord, path_points):
    """Finds the closest point (by sequence number) on the static path to a bus."""
    closest_dist = float('inf')
    closest_index = -1
    for i, point in enumerate(path_points):
        point_coord = (float(point['lat']), float(point['lng']))
        dist = haversine(bus_coord, point_coord)
        if dist < closest_dist:
            closest_dist = dist
            closest_index = i
    return closest_index

def calculate_distance_along_path(start_index, end_index, path_points):
    """Sums the distance of all segments in the path_points list."""
    total_distance_m = 0
    if start_index == -1 or end_index == -1 or start_index >= end_index:
        return 0
    for i in range(start_index, end_index):
        p1 = (float(path_points[i]['lat']), float(path_points[i]['lng']))
        p2 = (float(path_points[i+1]['lat']), float(path_points[i+1]['lng']))
        total_distance_m += haversine(p1, p2, unit=Unit.METERS)
    return total_distance_m

def generate_bus_aunty_html():
    """The main logic for the Bus Aunty. Fetches data, calculates ETAs, and generates an HTML file."""
    print("  > 🚌 Generating Bus Aunty HTML...")
    html_blocks = []
    
    for stop_config in STOPS_TO_MONITOR:
        direction = stop_config['direction']
        target_stop_id = stop_config['stopId']
        
        static_data = get_static_data_from_firebase(direction)
        live_buses = get_live_data_from_firebase(direction)
        
        if not static_data or 'busStopList' not in static_data or 'pointList' not in static_data:
            print(f"  > Skipping {stop_config['name']}: Missing static data.")
            continue
            
        target_stop = next((s for s in static_data['busStopList'] if s['stopId'] == target_stop_id), None)
        if not target_stop:
            print(f"  > Skipping {stop_config['name']}: Could not find stopId {target_stop_id}")
            continue

        stop_coord = (float(target_stop['lat']), float(target_stop['lng']))
        stop_path_index = find_closest_point_on_path(stop_coord, static_data['pointList'])
        
        walk_dist_m = haversine(USER_LOCATION, stop_coord, unit=Unit.METERS)
        walk_time_min = (walk_dist_m / AVG_WALK_SPEED_MPS) / 60
        
        closest_bus_dist_m = float('inf')
        
        for bus in live_buses:
            bus_coord = (float(bus['lat']), float(bus['lng']))
            bus_path_index = find_closest_point_on_path(bus_coord, static_data['pointList'])
            
            if bus_path_index < stop_path_index:
                dist_m = calculate_distance_along_path(bus_path_index, stop_path_index, static_data['pointList'])
                if dist_m < closest_bus_dist_m:
                    closest_bus_dist_m = dist_m
        
        final_eta_str = "--"
        if closest_bus_dist_m != float('inf'):
            bus_eta_min = (closest_bus_dist_m / AVG_BUS_SPEED_MPS) / 60
            magic_eta_min = bus_eta_min - walk_time_min
            
            if magic_eta_min <= 0.5: final_eta_str = "Now"
            elif magic_eta_min < 1: final_eta_str = "<1"
            else: final_eta_str = str(int(round(magic_eta_min)))
        
        html_blocks.append(f"""
            <div class="stop-card">
                <div class="eta-number">{final_eta_str}</div>
                <div class="route-info">
                    <div class="route-name">99</div>
                    <div class="stop-name">{stop_config['name']}</div>
                </div>
            </div>
        """)

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="30">
        <title>Bus Aunty</title>
        <style>
            body {{
                background-color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                margin: 0; padding: 16px; display: flex;
                flex-direction: column; gap: 16px;
            }}
            .stop-card {{
                display: flex; align-items: center; background-color: #f0f0f0;
                border-radius: 12px; padding: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .eta-number {{
                font-size: 80px; font-weight: bold; color: #000000;
                width: 120px; text-align: center;
            }}
            .route-info {{ display: flex; flex-direction: column; margin-left: 16px; }}
            .route-name {{ font-size: 32px; font-weight: 600; color: #000; }}
            .stop-name {{ font-size: 24px; color: #555; }}
            .header {{ font-size: 20px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="header">BusPal (Updated: {datetime.datetime.now().strftime('%I:%M:%S %p')})</div>
        {''.join(html_blocks)}
    </body>
    </html>
    """
    
    try:
        # Use the corrected path
        html_file_path = os.path.join(HOSTING_PUBLIC_PATH, "bus_aunty.html")
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"  > ✅ Successfully generated 'bus_aunty.html' at {html_file_path}")
        return True
    except Exception as e:
        print(f"  > ❌ CRITICAL ERROR: Could not write HTML file: {e}")
        return False

def deploy_to_firebase_hosting():
    """Runs the 'firebase deploy' command to upload the new HTML."""
    print("  > 🚀 Deploying to Firebase Hosting...")
    try:
        # Use the corrected path
        subprocess.run(["firebase", "deploy", "--only", "hosting"], 
                       cwd=PROJECT_ROOT_PATH, # Run from the project root
                       check=True, shell=True, capture_output=True, text=True)
        print("  > ✅ Deploy complete! Your Kindle can now refresh.")
    except subprocess.CalledProcessError as e:
        print(f"  > ❌ CRITICAL ERROR: Could not deploy to Firebase.")
        print(f"  > STDOUT: {e.stdout}")
        print(f"  > STDERR: {e.stderr}")
    except Exception as e:
        print(f"  > ❌ CRITICAL ERROR: Could not deploy to Firebase: {e}")

# ---------------------------------------------
# --- DATA COLLECTOR FUNCTIONS (v4.4) ---
# ---------------------------------------------

def get_full_route_data(api_url):
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=10)
        response.raise_for_status() 
        data = response.json()
        if data.get('pathList'):
            return data['pathList'][0]
        return None
    except Exception as e:
        print(f"  > Error fetching data from API: {e}")
        return None 

### <<< FIX 2: THIS FUNCTION WAS MISSING. I HAVE ADDED IT BACK. ---
def save_live_to_firebase(buses, direction_id):
    """
    SAVES ALL BUSES FOR ONE DIRECTION TO A *SINGLE* DOCUMENT.
    This is the Firebase Quota Fix (v4.4).
    """
    if not buses:
        buses = []
        
    try:
        doc_ref = db.collection("live_data").document(f"route99_dir_{direction_id}")
        live_bus_list = []
        for bus in buses:
            live_bus_list.append({
                'busId': bus.get('busId'),
                'lat': bus.get('lat'),
                'lng': bus.get('lng'),
                'bearing': bus.get('bearing')
            })
        doc_data = {
            'buses': live_bus_list,
            'bus_count': len(live_bus_list),
            'last_seen': firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(doc_data) # <-- This is now ONE write, not 40
        return len(live_bus_list)
    except Exception as e:
        print(f"  > ❌ Error saving LIVE data to Firebase: {e}")
        return 0
### --- END OF FIX 2 ---

def save_historical_to_csv(buses, ping_time, is_night_log):
    if not buses: return 0
    today_str = ping_time.strftime("%Y-%m-%d")
    file_suffix = "_night" if is_night_log else ""
    filename = os.path.join(HISTORICAL_DATA_PATH, f"log_{today_str}{file_suffix}.csv")
    new_data = []
    for bus in buses:
        new_data.append({
            'ping_time': ping_time.isoformat(), 'busId': bus.get('busId'),
            'lat': bus.get('lat'), 'lng': bus.get('lng'), 'bearing': bus.get('bearing'),
            'direction': bus.get('direction'), 'plateNumber': bus.get('plateNumber'),
            'stopId': bus.get('stopId'), 'load': bus.get('load', 'N/A')
        })
    if not new_data: return 0
    df = pd.DataFrame(new_data)
    file_exists = os.path.isfile(filename)
    try:
        df.to_csv(filename, mode='a', header=not file_exists, index=False)
        return len(new_data)
    except Exception as e:
        print(f"  > ❌ CSV ERROR: {e}"); return 0

def save_static_data_to_firebase(full_route_data, direction_id):
    try:
        doc_ref = db.collection("static_route_data").document(f"route_99_dir_{direction_id}")
        doc = doc_ref.get()
        if doc.exists:
            last_updated = doc.to_dict().get('last_updated')
            if last_updated and last_updated.date() == datetime.date.today():
                return True 
        static_data = {
            'pointList': full_route_data.get('pointList', []),
            'busStopList': full_route_data.get('busStopList', []),
            'scheduleList': full_route_data.get('scheduleList', []),
            'last_updated': firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(static_data); print(f"  > ✅ Saved STATIC data dir {direction_id}.")
        return True
    except Exception as e:
        print(f"  > Error saving STATIC data: {e}"); return False

def append_status_log(message):
    filename = os.path.join(HISTORICAL_DATA_PATH, "status_log.txt")
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception as e:
        print(f"  > Error writing to status_log.txt: {e}")

def notify_n8n(url, payload):
    print(f"  > [n8n SKIPPED]: Would send: {payload.get('message', 'No msg')}")


# --- MAIN LOOP (v4.4) ---
if __name__ == "__main__":
    
    consecutive_errors = 0
    total_ping_count = 0
    ping_streak = 0
    best_streak = 0
    
    ### <<< FIX 1.b: Create the data directory if it doesn't exist
    if not os.path.exists(HISTORICAL_DATA_PATH):
        os.makedirs(HISTORICAL_DATA_PATH)
        print(f"✅ Created data directory at {HISTORICAL_DATA_PATH}")
    ### --- END OF FIX 1.b ---
    
    print("--- 🚌 BusPal Data Collector & Aunty Generator (v4.4): Engaged! ---")
    append_status_log(f"\n--- SCRIPT STARTED: {datetime.datetime.now().isoformat()} ---")
    
    while True:
        current_time = datetime.datetime.now()
        is_active_hours = current_time.hour >= ACTIVE_HOUR_START or current_time.hour < ACTIVE_HOUR_END
        
        # --- 1. SETTINGS ---
        if is_active_hours:
            is_night_log = False
            sleep_duration = random.uniform(30, 45)
            print(f"--- Fetching new data (Timestamp: {current_time.isoformat()}) ---")
        else:
            is_night_log = True
            sleep_duration = 30 * 60 
            if ping_streak > 0: append_status_log(f"{current_time.isoformat()} - Streak: {ping_streak}.")
            print(f"Zzz... (It's {current_time.strftime