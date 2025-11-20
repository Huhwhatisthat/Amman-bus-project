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

# --- CONFIGURATION v6.1 ---

# 1. YOUR LOCATION
USER_LOCATION = (32.00247, 35.87108) 
AVG_WALK_SPEED_MPS = 1.3 
AVG_BUS_SPEED_MPS = 8.3  

# 2. ROUTES TO TRACK
# We track all Fast Lane routes
ROUTES_TO_TRACK = ["98", "99", "100"]

# 3. MONITOR SETTINGS (The "Flow" Dashboard)
# We assume IDs are shared across routes/directions for BRT stations.
STOPS_TO_MONITOR = []

# Helper to generate the config for all 3 routes
target_stops = [
    {"id": "10620", "name": "Mahmoud Alkiswani"},
    {"id": "10618", "name": "Agri. College"},
    {"id": "10617", "name": "Uni. of Jordan"},
    {"id": "10619", "name": "J.U. Hospital"}
]

for route in ROUTES_TO_TRACK:
    for stop in target_stops:
        # Add Direction 0 (e.g., To Museum)
        STOPS_TO_MONITOR.append({
            "name": f"{stop['name']} (Dir 0)",
            "stopId": stop['id'],
            "direction": 0,
            "route": route
        })
        # Add Direction 1 (e.g., To Swaileh)
        STOPS_TO_MONITOR.append({
            "name": f"{stop['name']} (Dir 1)",
            "stopId": stop['id'],
            "direction": 1,
            "route": route
        })

# 4. PATHS
SERVICE_KEY_PATH = r"D:\beaning\bean\serviceAccountKey.json"
PROJECT_ROOT_PATH = r"C:\Users\user\Desktop\Amman-bus-project" 
HISTORICAL_DATA_PATH = os.path.join(PROJECT_ROOT_PATH, "data")
HOSTING_PUBLIC_PATH = os.path.join(PROJECT_ROOT_PATH, "public") 

ACTIVE_HOUR_START = 6
ACTIVE_HOUR_END = 0 

# --- FIREBASE SETUP ---
try:
    cred = credentials.Certificate(SERVICE_KEY_PATH)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Successfully connected to Firebase!")
except FileNotFoundError:
    print(f"❌ ERROR: 'serviceAccountKey.json' not found at {SERVICE_KEY_PATH}")
    exit()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'Referer': 'https://online.ammanbus.jo/',
    'Origin': 'https://online.ammanbus.jo'
}

# --- HELPER FUNCTIONS ---

def get_full_route_data(route_code, direction):
    url = f"https://mobile.ammanbus.jo/rl1//web/pathInfo?region=116&lang=en&authType=4&direction={direction}&displayRouteCode={route_code}&resultType=111111"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status() 
        data = response.json()
        return data['pathList'][0] if data.get('pathList') else None
    except: return None 

def get_static_data_from_firebase(route, direction):
    try:
        doc_name = f"route_{route}_dir_{direction}"
        doc = db.collection("static_route_data").document(doc_name).get()
        return doc.to_dict() if doc.exists else None
    except: return None

def get_live_data_from_firebase(route, direction):
    try:
        doc_name = f"route_{route}_dir_{direction}"
        doc = db.collection("live_data").document(doc_name).get()
        return doc.to_dict().get('buses', []) if doc.exists else []
    except: return []

def find_closest_point_on_path(bus_coord, path_points):
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
    total_distance_m = 0
    if start_index == -1 or end_index == -1 or start_index >= end_index:
        return 0
    for i in range(start_index, end_index):
        p1 = (float(path_points[i]['lat']), float(path_points[i]['lng']))
        p2 = (float(path_points[i+1]['lat']), float(path_points[i+1]['lng']))
        total_distance_m += haversine(p1, p2, unit=Unit.METERS)
    return total_distance_m

# --- DATA SAVING ---

def save_live_to_firebase(buses, route, direction_id):
    if not buses: buses = []
    try:
        doc_name = f"route_{route}_dir_{direction_id}"
        doc_ref = db.collection("live_data").document(doc_name)
        live_bus_list = [{'busId': b.get('busId'), 'lat': b.get('lat'), 'lng': b.get('lng'), 'bearing': b.get('bearing'), 'load': b.get('load', '?')} for b in buses]
        doc_ref.set({'buses': live_bus_list, 'last_seen': firestore.SERVER_TIMESTAMP})
        return len(live_bus_list)
    except: return 0

def save_historical_to_csv(buses, ping_time, is_night_log):
    if not buses: return 0
    today = ping_time.strftime("%Y-%m-%d")
    suffix = "_night" if is_night_log else ""
    filename = os.path.join(HISTORICAL_DATA_PATH, f"log_{today}{suffix}.csv")
    new_data = []
    for b in buses:
        new_data.append({
            'ping_time': ping_time.isoformat(), 
            'route': b.get('route'), 
            'busId': b.get('busId'),
            'lat': b.get('lat'), 'lng': b.get('lng'), 'bearing': b.get('bearing'),
            'direction': b.get('direction'), 'plateNumber': b.get('plateNumber'),
            'stopId': b.get('stopId'), 'load': b.get('load', 'N/A')
        })
    df = pd.DataFrame(new_data)
    file_exists = os.path.isfile(filename)
    try: df.to_csv(filename, mode='a', header=not file_exists, index=False)
    except: pass
    return len(new_data)

def save_static_data_to_firebase(full_route_data, route, direction_id):
    try:
        doc_name = f"route_{route}_dir_{direction_id}"
        doc_ref = db.collection("static_route_data").document(doc_name)
        doc = doc_ref.get()
        if doc.exists and doc.to_dict().get('last_updated', datetime.datetime(2000,1,1)).date() == datetime.date.today().date():
            return True
        doc_ref.set({
            'pointList': full_route_data.get('pointList', []),
            'busStopList': full_route_data.get('busStopList', []),
            'last_updated': firestore.SERVER_TIMESTAMP
        })
        print(f"  > ✅ Saved STATIC data for Route {route} Dir {direction_id}.")
        
        # --- DEBUG MODE: OFF (Commented out as requested) ---
        # print(f"\n--- STOPS FOR ROUTE {route} DIR {direction_id} ---")
        # for stop in full_route_data.get('busStopList', []):
        #     print(f"ID: {stop['stopId']} | Name: {stop['stopName']}")
        # print("----------------------------------------\n")
        
        return True
    except: return False

def append_status_log(message):
    try:
        with open(os.path.join(HISTORICAL_DATA_PATH, "status_log.txt"), "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except: pass

# --- GENERATE HTML ---

def generate_bus_aunty_html():
    print("  > 🚌 Generating Bus Aunty HTML (Multi-Stop)...")
    html_cards = []
    
    for stop_config in STOPS_TO_MONITOR:
        route = stop_config['route']
        direction = stop_config['direction']
        target_stop_id = stop_config['stopId']
        
        static_data = get_static_data_from_firebase(route, direction)
        live_buses = get_live_data_from_firebase(route, direction)
        
        if not static_data: continue
            
        target_stop = next((s for s in static_data.get('busStopList', []) if s['stopId'] == target_stop_id), None)
        if not target_stop: continue # Skip invalid stops silently

        stop_coord = (float(target_stop['lat']), float(target_stop['lng']))
        stop_path_index = find_closest_point_on_path(stop_coord, static_data['pointList'])
        
        walk_dist_m = haversine(USER_LOCATION, stop_coord, unit=Unit.METERS)
        walk_time_min = (walk_dist_m / AVG_WALK_SPEED_MPS) / 60
        
        upcoming_buses = [] 
        
        for bus in live_buses:
            bus_coord = (float(bus['lat']), float(bus['lng']))
            bus_path_index = find_closest_point_on_path(bus_coord, static_data['pointList'])
            
            if bus_path_index < stop_path_index:
                dist_m = calculate_distance_along_path(bus_path_index, stop_path_index, static_data['pointList'])
                bus_travel_time = (dist_m / AVG_BUS_SPEED_MPS) / 60
                leave_in_min = bus_travel_time - walk_time_min
                
                upcoming_buses.append({'leave_in': leave_in_min, 'load': bus.get('load', '?')})
        
        upcoming_buses.sort(key=lambda x: x['leave_in'])
        
        main_eta = "--"
        sub_text = "No Bus"
        next_bus_text = "Next: --"
        
        if upcoming_buses:
            first_bus = upcoming_buses[0]
            val = first_bus['leave_in']
            
            if val > 1:
                main_eta = str(int(round(val)))
                sub_text = "min to leave"
            elif val > 0:
                main_eta = "<1"
                sub_text = "Run!"
            else:
                main_eta = "NOW"
                sub_text = f"({abs(int(val))} min ago)"
                
            if len(upcoming_buses) > 1:
                second_bus = upcoming_buses[1]
                val_2 = int(round(second_bus['leave_in']))
                load_2 = second_bus['load']
                next_bus_text = f"Next: {val_2} min (L:{load_2})"

        html_cards.append(f"""
            <div class="stop-card">
                <div class="card-header">
                    <span class="route-badge">{route}</span>
                    <span class="stop-name">{stop_config['name']}</span>
                </div>
                <div class="eta-container">
                    <div class="eta-main">{main_eta}</div>
                    <div class="eta-sub">{sub_text}</div>
                </div>
                <div class="footer">{next_bus_text}</div>
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
                font-family: Helvetica, Arial, sans-serif;
                margin: 0; padding: 10px;
                min-height: 100vh;
                box-sizing: border-box;
                /* 2-Column Grid */
                display: grid;
                grid-template-columns: 1fr 1fr; 
                gap: 10px;
                align-content: start;
            }}
            .stop-card {{
                background-color: #f4f4f4;
                border: 2px solid #000;
                border-radius: 8px;
                display: flex;
                flex-direction: column;
                padding: 10px;
                min-height: 140px;
            }}
            .card-header {{
                display: flex; justify-content: flex-start; align-items: center; gap: 8px;
                border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-bottom: 5px;
            }}
            .stop-name {{ font-size: 1em; font-weight: bold; color: #333; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }}
            .route-badge {{ 
                background: #000; color: #fff; padding: 2px 6px; 
                border-radius: 4px; font-weight: bold; font-size: 1.1em;
            }}
            .eta-container {{
                flex-grow: 1; display: flex; flex-direction: column;
                justify-content: center; align-items: center;
            }}
            .eta-main {{ font-size: 3.5em; font-weight: 800; line-height: 1; }}
            .eta-sub {{ font-size: 0.9em; color: #555; margin-top: 2px; font-weight: bold; }}
            .footer {{
                margin-top: auto; border-top: 1px solid #ccc; padding-top: 5px;
                text-align: center; font-size: 0.8em; color: #444;
            }}
            .timestamp {{ position: fixed; bottom: 5px; right: 5px; font-size: 0.7em; color: #aaa; background: rgba(255,255,255,0.8); padding: 2px; }}
        </style>
    </head>
    <body>
        {''.join(html_cards)}
        <div class="timestamp">Updated: {datetime.datetime.now().strftime('%I:%M %p')}</div>
    </body>
    </html>
    """
    
    try:
        html_file_path = os.path.join(HOSTING_PUBLIC_PATH, "bus_aunty.html")
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        return True
    except Exception as e:
        print(f"  > ❌ HTML Generation Error: {e}")
        return False

def deploy_to_firebase_hosting():
    print("  > 🚀 Deploying to Firebase...")
    try:
        subprocess.run(["firebase", "deploy", "--only", "hosting"], 
                       cwd=PROJECT_ROOT_PATH, check=True, shell=True, capture_output=True)
        print("  > ✅ Deploy complete!")
    except: print("  > ❌ Deploy Error")

# --- MAIN LOOP ---
if __name__ == "__main__":
    if not os.path.exists(HISTORICAL_DATA_PATH): os.makedirs(HISTORICAL_DATA_PATH)
    print("--- 🚌 BusPal v6.1 (Multi-Stop Flow): Engaged! ---")
    append_status_log(f"\n--- STARTED v6.1 at {datetime.datetime.now().isoformat()} ---")
    
    consecutive_errors = 0
    total_ping_count = 0
    ping_streak = 0
    
    while True:
        now = datetime.datetime.now()
        is_active = ACTIVE_HOUR_START <= now.hour or now.hour < ACTIVE_HOUR_END
        
        print(f"\n--- Fetching ({now.strftime('%H:%M:%S')}) ---")
        
        api_success = False
        total_buses = 0
        all_buses_csv = []
        
        # LOOP THROUGH ALL ROUTES
        for route in ROUTES_TO_TRACK:
            for d in [0, 1]: # Directions
                data = get_full_route_data(route, d)
                if data:
                    api_success = True
                    buses = data.get('busList', [])
                    
                    if buses: print(f"  > Route {route} Dir {d}: Found {len(buses)} buses.")
                    
                    if buses:
                        if is_active: total_buses += save_live_to_firebase(buses, route, d)
                        for b in buses: 
                            b['direction'] = d
                            b['route'] = route
                        all_buses_csv.extend(buses)
                    
                    if is_active and data.get('pointList'): 
                        save_static_data_to_firebase(data, route, d)

        if api_success:
            consecutive_errors = 0
            total_ping_count += 1
            ping_streak += 1
            save_historical_to_csv(all_buses_csv, now, not is_active)
            
            summary = f"Saved {total_buses} buses across {len(ROUTES_TO_TRACK)} routes. Streak: {ping_streak}."
            print(f"  > {summary}")
            
            if ping_streak % 10 == 0: append_status_log(f"{now.isoformat()} - {summary}")
            
            if generate_bus_aunty_html():
                if total_ping_count % 5 == 0: deploy_to_firebase_hosting()
        else:
            consecutive_errors += 1
            print(f"  > ❌ API Error. Strike {consecutive_errors}")
            ping_streak = 0
        
        if consecutive_errors >= 5: break
        
        sleep_duration = random.uniform(30, 45)
        print(f"Waiting {sleep_duration:.1f} seconds...")
        time.sleep(sleep_duration)