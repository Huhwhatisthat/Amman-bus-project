import requests
import json
import time
import random
import datetime
import pandas as pd
import os
import firebase_admin
from firebase_admin import credentials, firestore

# --- SCRIPT CONFIGURATION ---
# --- (All your settings in one place) ---

# n8n URLs are commented out as requested
# N8N_FAILURE_URL = "YOUR_FAILURE_URL_HERE"
# N8N_STATUS_URL = "YOUR_STATUS_URL_HERE"

SERVICE_KEY_PATH = r"D:\beaning\bean\serviceAccountKey.json"
HISTORICAL_DATA_PATH = r"C:\Users\user\Desktop\Amman bus project\The precious data"

API_URLS = {
    0: "https://mobile.ammanbus.jo/rl1//web/pathInfo?region=116&lang=en&authType=4&direction=0&displayRouteCode=99&resultType=111111",
    1: "https://mobile.ammanbus.jo/rl1//web/pathInfo?region=116&lang=en&authType=4&direction=1&displayRouteCode=99&resultType=111111"
}

# Active hours
ACTIVE_HOUR_START = 6  # 6 AM
ACTIVE_HOUR_END = 0    # Midnight (we check for > 6 OR < 0)

# --- "Morale" Settings ---
GERMAN_QUOTES = [
    ("Wo ein Wille ist, da ist auch ein Weg.", "Where there's a will, there's a way. - German Proverb"),
    ("Ohne Fleiß kein Preis.", "No pain, no gain. - German Proverb"),
    ("Ordnung muss sein.", "There must be order. - German Proverb")
]
MORALE_PING_TARGETS = [100, 500, 1000, 2500, 5000, 10000] # Notify at these TOTAL pings

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


def get_full_route_data(api_url):
    """Pings the API and returns the full pathList object."""
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

def save_live_to_firebase(buses, direction_id):
    """
    SAVES ALL BUSES FOR ONE DIRECTION TO A *SINGLE* DOCUMENT.
    This is the Firebase Quota Fix.
    """
    if not buses:
        # If no buses, we still write an empty list to show the route is empty
        buses = []
        
    try:
        # We will store all live data in one collection
        doc_ref = db.collection("live_data").document(f"route99_dir_{direction_id}")
        
        # Prepare data: just the essentials for the "live" app
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
        
        # This is now just ONE write operation
        doc_ref.set(doc_data) 
        return len(live_bus_list)
        
    except Exception as e:
        print(f"  > ❌ Error saving LIVE data to Firebase: {e}")
        return 0

def save_historical_to_csv(buses, ping_time, is_night_log):
    """Saves HISTORICAL bus data to a local CSV file."""
    if not buses:
        return 0

    today_str = ping_time.strftime("%Y-%m-%d")
    
    # NEW: Use a different filename for night logs
    file_suffix = "_night" if is_night_log else ""
    filename = os.path.join(HISTORICAL_DATA_PATH, f"log_{today_str}{file_suffix}.csv")
    
    new_data = []
    for bus in buses:
        new_data.append({
            'ping_time': ping_time.isoformat(),
            'busId': bus.get('busId'),
            'lat': bus.get('lat'),
            'lng': bus.get('lng'),
            'bearing': bus.get('bearing'),
            'direction': bus.get('direction'),
            'plateNumber': bus.get('plateNumber'),
            'stopId': bus.get('stopId'),
            'disabledPerson': bus.get('disabledPerson'),
            'vehicleType': bus.get('vehicleType'),
            'ac': bus.get('ac'),
            'bike': bus.get('bike'),
            'load': bus.get('load', 'N/A') # <-- Added the 'load' metric
        })

    if not new_data:
        return 0

    df = pd.DataFrame(new_data)
    file_exists = os.path.isfile(filename)
    
    try:
        df.to_csv(filename, mode='a', header=not file_exists, index=False)
        return len(new_data)
    except Exception as e:
        print(f"  > ❌ CRITICAL ERROR: Could not save HISTORICAL data to CSV at {filename}.")
        print(f"  > Error: {e}")
        return 0

def save_static_data_to_firebase(full_route_data, direction_id):
    """Saves the STATIC route data (points, stops) to Firebase ONCE per day."""
    try:
        doc_ref = db.collection("static_route_data").document(f"route_99_dir_{direction_id}")
        doc = doc_ref.get()
        if doc.exists:
            last_updated = doc.to_dict().get('last_updated')
            if last_updated and last_updated.date() == datetime.date.today():
                return True # Already saved today, skip.

        static_data = {
            'pointList': full_route_data.get('pointList', []),
            'busStopList': full_route_data.get('busStopList', []),
            'scheduleList': full_route_data.get('scheduleList', []),
            'last_updated': firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(static_data)
        print(f"  > ✅ Successfully saved STATIC data for direction {direction_id}.")
        return True
    except Exception as e:
        print(f"  > Error saving STATIC data: {e}")
        return False

def append_status_log(message):
    """Appends a summary message to a local status_log.txt file."""
    filename = os.path.join(HISTORICAL_DATA_PATH, "status_log.txt")
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception as e:
        print(f"  > Error writing to status_log.txt: {e}")

# --- n8n functions are "commented out" by disabling the call ---
def notify_n8n(url, payload):
    # As requested, n8n calls are disabled.
    # We will just print what we *would* have sent.
    print(f"  > [n8n SKIPPED]: Would have sent: {payload.get('message', 'No message')}")
    return
    # if not url.startswith("https://"):
    #     return
    # try:
    #     requests.post(url, json=payload, timeout=5)
    #     print(f"  > ✅ Successfully sent notification to n8n: {payload.get('message', 'Status update')}")
    # except Exception as e:
    #     print(f"  > ❌ FAILED to send n8n notification: {e}")

# --- Main part of the script ---
if __name__ == "__main__":
    
    consecutive_errors = 0
    total_ping_count = 0
    ping_streak = 0
    best_streak = 0
    script_start_time = datetime.datetime.now()
    
    print("--- 🚌 BusPal Data Collector: Engaged! ---")
    append_status_log(f"\n--- SCRIPT STARTED: {script_start_time.isoformat()} ---")
    
    while True:
        current_time = datetime.datetime.now()
        is_active_hours = current_time.hour >= ACTIVE_HOUR_START or current_time.hour < ACTIVE_HOUR_END
        
        # --- 1. SETTINGS based on time of day ---
        if is_active_hours:
            is_night_log = False
            sleep_duration = random.uniform(30, 45)
            print(f"--- Fetching new data (Timestamp: {current_time.isoformat()}) ---")
        else:
            # NIGHT MODE
            is_night_log = True
            sleep_duration = 30 * 60 # 30 minutes
            if ping_streak > 0: # Log the final streak before sleeping
                append_status_log(f"{current_time.isoformat()} - Streak: {ping_streak}. Best: {best_streak}.")
            
            print(f"Zzz... (It's {current_time.strftime('%H:%M')}). In night mode. Checking again in 30 mins.")
            append_status_log(f"{current_time.isoformat()} - Entering night mode. Gute Nacht!")
            ping_streak = 0
        
        # --- 2. FETCH DATA ---
        total_buses_found_live = 0
        all_buses_for_csv = []
        api_success = False

        for direction, url in API_URLS.items():
            full_data = get_full_route_data(url)
            if full_data:
                api_success = True 
                live_buses = full_data.get('busList', [])
                
                # We save *all* buses after hours, to see where they park
                # This confirms your theory!
                
                if live_buses:
                    # Save to Firebase (Live) - Only during active hours
                    if is_active_hours:
                        total_buses_found_live += save_live_to_firebase(live_buses, direction)
                    
                    # Prep for CSV (always, even at night)
                    for bus in live_buses:
                        bus['direction'] = direction
                    all_buses_for_csv.extend(live_buses)
                
                # Save Static Data (once per day, only during active hours)
                if is_active_hours and full_data.get('pointList'):
                    save_static_data_to_firebase(full_data, direction)
        
        # --- 3. PROCESS THE RESULTS ---
        if api_success:
            total_ping_count += 1 # NEW: Total counter
            consecutive_errors = 0
            
            # Save to historical CSV
            csv_count = save_historical_to_csv(all_buses_for_csv, current_time, is_night_log)
            
            if is_active_hours:
                ping_streak += 1
                if ping_streak > best_streak:
                    best_streak = ping_streak
                
                summary = f"SUCCESS: Saved {total_buses_found_live} Firebase, {csv_count} CSV. Streak: {ping_streak}. Total Pings: {total_ping_count}"
                print(f"  > {summary}")
                
                if ping_streak % 10 == 0:
                    append_status_log(f"{current_time.isoformat()} - {summary}")
                
                # NEW: Morale Check on TOTAL pings
                if total_ping_count in MORALE_PING_TARGETS:
                    print(f"\n  > GLÜCKWUNSCH! {total_ping_count} total successful pings! Weiter so! (Keep it up!)\n")
                    append_status_log(f"{current_time.isoformat()} - !!! TOTAL PING MILESTONE: {total_ping_count} !!!")
                    # status_payload = {"message": f"BusPal Milestone: {total_ping_count} total pings!"}
                    # notify_n8n(N8N_STATUS_URL, status_payload) # This is where the status ping would go
            
            else:
                # Night log summary
                summary = f"NIGHT LOG: Saved {csv_count} parked bus locations to CSV."
                print(f"  > {summary}")
                append_status_log(f"{current_time.isoformat()} - {summary}")

        else:
            # FAILURE!
            consecutive_errors += 1
            print(f"  > ❌ Could not retrieve ANY bus data. Strike {consecutive_errors} of 5.")
            
            if ping_streak > 0:
                print(f"  > Streak lost at {ping_streak} pings. Best: {best_streak}")
                quote, attribution = random.choice(GERMAN_QUOTES)
                print(f"  > Ach, schade! '{quote}' ({attribution})\n")
                append_status_log(f"{current_time.isoformat()} - STREAK LOST at {ping_streak}. Best: {best_streak}. Ach, schade!")
            
            ping_streak = 0 

        # --- 4. CHECK FOR 5-STRIKE FAILURE ---
        if consecutive_errors >= 5:
            print("\n❌ STOPPING SCRIPT: 5 consecutive errors.")
            error_msg = f"{current_time.isoformat()} - STOPPING SCRIPT. 5 consecutive errors."
            append_status_log(error_msg)
            
            # notify_n8n(N8N_FAILURE_URL, {"message": error_msg})
            break 

        # --- 5. WAIT FOR NEXT CYCLE ---
        print(f"\nWaiting for {sleep_duration:.1f} seconds...\n")
        time.sleep(sleep_duration)