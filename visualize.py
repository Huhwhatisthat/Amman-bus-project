import firebase_admin
from firebase_admin import credentials, firestore
import folium # <-- Our new mapping library
import os

# --- CONFIGURATION ---
SERVICE_KEY_PATH = r"D:\beaning\bean\serviceAccountKey.json"
HOSTING_PUBLIC_PATH = os.path.join(r"C:\Users\user\Desktop\Amman-bus-project", "public")
HTML_FILENAME = "interpolation_map.html"

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

def get_static_data_from_firebase(direction):
    """Fetches the static route path and stop list from Firebase."""
    doc_ref = db.collection("static_route_data").document(f"route_99_dir_{direction}")
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    else:
        print(f"  > WARNING: No static data found for direction {direction}.")
        return None

def get_live_data_from_firebase(direction):
    """Fetches the live bus list from Firebase."""
    doc_ref = db.collection("live_data").document(f"route99_dir_{direction}")
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('buses', [])
    else:
        print(f"  > WARNING: No live data found for direction {direction}.")
        return []

def create_map():
    print("--- 🗺️ Generating Live Map ---")
    
    # 1. Create a base map, centered on Amman
    m = folium.Map(location=[31.9539, 35.9106], zoom_start=12)
    
    # We will draw for both directions
    for direction in [0, 1]:
        print(f"  > Processing direction {direction}...")
        static_data = get_static_data_from_firebase(direction)
        live_buses = get_live_data_from_firebase(direction)
        
        color = 'blue' if direction == 0 else 'green'

        # 2. Draw the STATIC Route Path (pointList)
        if static_data and 'pointList' in static_data:
            path_points = [(float(p['lat']), float(p['lng'])) for p in static_data['pointList']]
            folium.PolyLine(
                path_points,
                color=color,
                weight=5,
                opacity=0.7
            ).add_to(m)
            print(f"  > Drew route path for direction {direction}.")

        # 3. Draw the STATIC Bus Stops (busStopList)
        if static_data and 'busStopList' in static_data:
            for stop in static_data['busStopList']:
                folium.CircleMarker(
                    location=[float(stop['lat']), float(stop['lng'])],
                    radius=5,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=1,
                    popup=f"STOP: {stop['stopName']} (ID: {stop['stopId']})"
                ).add_to(m)
            print(f"  > Drew {len(static_data['busStopList'])} stops for direction {direction}.")

        # 4. Draw the LIVE Bus Icons
        if live_buses:
            for bus in live_buses:
                folium.Marker(
                    location=[float(bus['lat']), float(bus['lng'])],
                    popup=f"Bus {bus['busId']} (Dir: {direction})",
                    icon=folium.Icon(color='red', icon='bus', prefix='fa') # FontAwesome bus icon
                ).add_to(m)
            print(f"  > Drew {len(live_buses)} live buses for direction {direction}.")

    # 5. Save the map to an HTML file
    map_path = os.path.join(HOSTING_PUBLIC_PATH, HTML_FILENAME)
    m.save(map_path)
    print(f"\n✅ --- Map saved to {map_path} ---")
    print(f"You can now view it at: https://no-way-chat.web.app/{HTML_FILENAME}")


if __name__ == "__main__":
    create_map()