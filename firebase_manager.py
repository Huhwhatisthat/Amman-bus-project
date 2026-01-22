import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import os
import datetime
import config

# --- INITIALIZATION ---
try:
    cred = credentials.Certificate(config.SERVICE_KEY_PATH)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ [Firebase] Connected successfully.")
except FileNotFoundError:
    print(f"❌ [Firebase] Key not found at {config.SERVICE_KEY_PATH}")
    exit()

# --- READ FUNCTIONS ---
def get_static_data(route, direction):
    try:
        doc_name = f"route_{route}_dir_{direction}"
        doc = db.collection("static_route_data").document(doc_name).get()
        return doc.to_dict() if doc.exists else None
    except: return None

def get_live_data(route, direction):
    try:
        doc_name = f"route_{route}_dir_{direction}"
        doc = db.collection("live_data").document(doc_name).get()
        return doc.to_dict().get('buses', []) if doc.exists else []
    except: return []

# --- WRITE FUNCTIONS ---
def save_live_data(buses, route, direction_id):
    if not buses: return 0
    try:
        doc_name = f"route_{route}_dir_{direction_id}"
        doc_ref = db.collection("live_data").document(doc_name)
        
        # We added 'velocity' and 'status' to the dictionary here
        live_bus_list = [
            {
                'busId': b.get('busId'), 
                'lat': b.get('lat'), 
                'lng': b.get('lng'), 
                'bearing': b.get('bearing'), 
                'load': b.get('load', '?'),
                'status': b.get('status', 'Unknown'),
                'velocity': b.get('velocity', 0) # NEW: Save speed to Firebase
            } for b in buses
        ]
        
        doc_ref.set({'buses': live_bus_list, 'last_seen': firestore.SERVER_TIMESTAMP})
        return len(live_bus_list)
    except Exception as e:
        print(f"Error saving live data: {e}")
        return 0

def save_static_data(full_route_data, route, direction_id):
    """
    Saves the map geometry (pointList) and stop locations to Firebase.
    Only updates once per day to save on database writes.
    """
    try:
        doc_name = f"route_{route}_dir_{direction_id}"
        doc_ref = db.collection("static_route_data").document(doc_name)
        doc = doc_ref.get()
        
        # Check if we already updated the map today
        if doc.exists:
            last_updated = doc.to_dict().get('last_updated')
            if last_updated and last_updated.date() == datetime.date.today():
                return True
                
        doc_ref.set({
            'pointList': full_route_data.get('pointList', []),
            'busStopList': full_route_data.get('busStopList', []),
            'last_updated': firestore.SERVER_TIMESTAMP
        })
        print(f"  > 🗺️ Saved STATIC map for Route {route} Dir {direction_id}.")
        return True
    except Exception as e:
        print(f"Error saving static data: {e}")
        return False

def save_historical_csv(buses, ping_time, is_night_log):
    if not buses: return 0
    today = ping_time.strftime("%Y-%m-%d")
    suffix = "_night" if is_night_log else ""
    filename = os.path.join(config.HISTORICAL_DATA_PATH, f"log_{today}{suffix}.csv")
    
    new_data = []
    for b in buses:
        new_data.append({
            'ping_time': ping_time.isoformat(), 
            'route': b.get('route'), 
            'busId': b.get('busId'),
            'lat': b.get('lat'), 
            'lng': b.get('lng'), 
            'bearing': b.get('bearing'),
            'direction': b.get('direction'), 
            'plateNumber': b.get('plateNumber'),
            'stopId': b.get('stopId'), 
            'load': b.get('load', 'N/A'),
            'status': b.get('status', 'Unknown'),
            'velocity': b.get('velocity', 0) # NEW: Save speed to your CSV logs
        })
    
    df = pd.DataFrame(new_data)
    file_exists = os.path.isfile(filename)
    try: 
        df.to_csv(filename, mode='a', header=not file_exists, index=False)
    except: pass
    return len(new_data)

def append_status_log(message):
    try:
        with open(os.path.join(config.HISTORICAL_DATA_PATH, "status_log.txt"), "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except: pass