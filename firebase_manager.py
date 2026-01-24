import os
import datetime
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import config  # <--- Crucial: This fixes the 'config not defined' error

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

def get_live_data_full(route, direction):
    """Returns the whole document (buses + last_seen timestamp)."""
    try:
        doc_name = f"route_{route}_dir_{direction}"
        doc = db.collection("live_data").document(doc_name).get()
        return doc.to_dict() if doc.exists else None
    except: return None

# --- WRITE FUNCTIONS ---
def save_live_data(buses, route, direction_id):
    if not buses: return 0
    try:
        doc_name = f"route_{route}_dir_{direction_id}"
        doc_ref = db.collection("live_data").document(doc_name)
        live_bus_list = [
            {
                'busId': b.get('busId'), 
                'lat': b.get('lat'), 
                'lng': b.get('lng'), 
                'bearing': b.get('bearing'), 
                'status': b.get('status', 'Unknown'),
                'velocity': b.get('velocity', 0)
            } for b in buses
        ]
        doc_ref.set({'buses': live_bus_list, 'last_seen': firestore.SERVER_TIMESTAMP})
        return len(live_bus_list)
    except Exception as e:
        print(f"Error saving live data: {e}")
        return 0

def save_static_data(full_route_data, route, direction_id):
    try:
        doc_name = f"route_{route}_dir_{direction_id}"
        doc_ref = db.collection("static_route_data").document(doc_name)
        doc_ref.set({
            'pointList': full_route_data.get('pointList', []),
            'busStopList': full_route_data.get('busStopList', []),
            'last_updated': firestore.SERVER_TIMESTAMP
        })
        return True
    except: return False

def save_historical_csv(buses, ping_time, is_night_mode):
    if not buses: return 0
    today = ping_time.strftime("%Y-%m-%d")
    
    # MODULAR LOG NAMING
    prefix = "NIGHT_" if is_night_mode else "DAY_"
    filename = os.path.join(config.HISTORICAL_DATA_PATH, f"{prefix}log_{today}.csv")
    
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
            'status': b.get('status', 'Unknown'),
            'velocity': b.get('velocity', 0)
        })
    
    df = pd.DataFrame(new_data)
    file_exists = os.path.isfile(filename)
    try: 
        df.to_csv(filename, mode='a', header=not file_exists, index=False)
    except: pass
    return len(new_data)