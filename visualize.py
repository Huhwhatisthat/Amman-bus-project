import firebase_admin
from firebase_admin import credentials, firestore
import folium
import os
import subprocess
import json
import requests 

# --- CONFIGURATION ---
SERVICE_KEY_PATH = r"D:\beaning\bean\serviceAccountKey.json"
PROJECT_ROOT_PATH = r"C:\Users\user\Desktop\Amman-bus-project"
HOSTING_PUBLIC_PATH = os.path.join(PROJECT_ROOT_PATH, "public")
HTML_FILENAME = "interpolation_map.html"
HOSTING_URL = "https://no-way-chat.web.app"
ANIMATION_JS_FILENAME = "Leaflet.AnimatedMarker.js"
ANIMATION_JS_URL = "https://unpkg.com/leaflet.animatedmarker@1.0.0/src/AnimatedMarker.js"

# --- YOUR FIREBASE WEB CONFIG ---
FIREBASE_CONFIG_OBJECT = {
  "apiKey": "AIzaSyDqEXaniP13SjvAC1fxicOQeoor04xxnmI",
  "authDomain": "no-way-chat.firebaseapp.com",
  "projectId": "no-way-chat",
  "storageBucket": "no-way-chat.firebasestorage.app",
  "messagingSenderId": "1083549262658",
  "appId": "1:1083549262658:web:1541718e26d8ae67b79edb"
}
# ---------------------------------------------

# --- FIREBASE ADMIN SETUP ---
try:
    cred = credentials.Certificate(SERVICE_KEY_PATH)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Successfully connected to Firebase (Admin)!")
except FileNotFoundError:
    print(f"❌ ERROR: 'serviceAccountKey.json' not found at {SERVICE_KEY_PATH}")
    exit()

def get_static_data_from_firebase(direction):
    """Fetches the static route path and stop list from Firebase."""
    doc_ref = db.collection("static_route_data").document(f"route_99_dir_{direction}")
    
    ### <<< FIX: This was the typo 'doc_get()' is now 'doc_ref.get()' ---
    doc = doc_ref.get()
    ### --- END OF FIX ---
    
    if doc.exists:
        return doc.to_dict()
    print(f"  > WARNING: No static data found for direction {direction}.")
    return None

def download_animation_library():
    """Downloads the JS file for animation and saves it to the public folder."""
    save_path = os.path.join(HOSTING_PUBLIC_PATH, ANIMATION_JS_FILENAME)
    if os.path.exists(save_path):
        print(f"  > Animation library '{ANIMATION_JS_FILENAME}' already exists.")
        return True
        
    print(f"  > Downloading '{ANIMATION_JS_FILENAME}'...")
    try:
        r = requests.get(ANIMATION_JS_URL, timeout=10)
        r.raise_for_status()
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(r.text)
        print(f"  > ✅ Successfully saved '{ANIMATION_JS_FILENAME}'.")
        return True
    except Exception as e:
        print(f"  > ❌ FAILED to download animation library: {e}")
        return False

def build_map_with_live_javascript():
    print("--- 🗺️ Building Live Interpolation Map (v1.2) ---")
    
    # 1. Create a base map
    m = folium.Map(location=[31.97, 35.89], zoom_start=13)
    
    # 2. Add the static paths and stops to the map
    for direction in [0, 1]:
        static_data = get_static_data_from_firebase(direction)
        color = 'blue' if direction == 0 else 'green'

        if static_data and 'pointList' in static_data:
            path_points = [(float(p['lat']), float(p['lng'])) for p in static_data['pointList']]
            folium.PolyLine(path_points, color=color, weight=5, opacity=0.7, popup=f"Direction {direction}").add_to(m)

        # --- THIS IS THE CORRECTED INDENTATION ---
        # This code block is now INSIDE the 'for' loop
        if static_data and 'busStopList' in static_data:
            # --- CUSTOM ICON CODE ---
            # Make sure this file is in your 'public' folder
            stop_icon_url = "bus-stop-icon-vector-illustration_1147484-8520.avif" 
            for stop in static_data['busStopList']:
                icon = folium.features.CustomIcon(
                    stop_icon_url,
                    icon_size=(30, 30), # (width, height)
                    icon_anchor=(15, 15) # center
                )
                folium.Marker(
                    location=[float(stop['lat']), float(stop['lng'])],
                    icon=icon,
                    popup=f"STOP: {stop['stopName']} (ID: {stop['stopId']})"
                ).add_to(m)
        # --- END OF INDENTATION FIX ---

    # 3. Save the base map to a string (This is OUTSIDE the loop)
    map_html_string = m.get_root().render()

    # 4. Get Firebase config
    firebase_config_string = json.dumps(FIREBASE_CONFIG_OBJECT)

    # 5. Define the JavaScript block
    javascript_block = f"""
    <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js"></script>
    <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-firestore.js"></script>
    <script src="{ANIMATION_JS_FILENAME}"></script>
    
    <script>
        // --- 1. INITIALIZE FIREBASE ---
        const firebaseConfig = {firebase_config_string};
        firebase.initializeApp(firebaseConfig);
        const db = firebase.firestore();
        console.log("Firebase Initialized!");

        let busMarkers = {{}};

        // --- 2. FUNCTION TO ADD/UPDATE A BUS ---
        function updateBusMarker(busData, direction) {{
            const busId = busData.busId;
            const pos = [parseFloat(busData.lat), parseFloat(busData.lng)];
            
            if (busMarkers[busId]) {{
                busMarkers[busId].moveTo(pos, 30000); // 30 second animation
            }} else {{
                console.log(`Creating new marker for bus ${{busId}}`);
                const icon = L.divIcon({{
                    // --- CUSTOM BUS ICON ---
                    // Make sure this file is in your 'public' folder
                    html: `<img src="Screenshot 2025-11-14 150909.png" style="width: 30px; height: 30px;">`,
                    className: '', // We don't need the extra CSS
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                }});
                busMarkers[busId] = L.animatedMarker([pos, pos], {{
                    icon: icon,
                    title: `Bus ${{busId}}`
                }}).addTo(map);
            }}
        }}

        // --- 3. LISTEN FOR LIVE DATA (FOR BOTH DIRECTIONS) ---
        function listenForBuses(direction) {{
            const docRef = db.collection("live_data").doc(`route99_dir_${{direction}}`);
            
            docRef.onSnapshot((doc) => {{
                if (doc.exists) {{
                    const data = doc.data();
                    const liveBuses = data.buses || [];
                    console.log(`Received ${{liveBuses.length}} buses for direction ${{direction}}`);
                    
                    liveBuses.forEach(bus => {{
                        updateBusMarker(bus, direction);
                    }});
                }} else {{
                    console.log(`No live data for direction ${{direction}}`);
                }}
            }});
        }}
        
        // --- 4. START THE LISTENERS ---
        setTimeout(() => {{
            const map = {m.get_name()}; // Get the Folium map variable
            console.log("Map loaded. Starting listeners...");
            listenForBuses(0);
            listenForBuses(1);
        }}, 1000); // Wait 1 second for the map to load

    </script>
    """

    # 6. Inject the JavaScript into the HTML
    final_html = map_html_string.replace("</body>", f"{javascript_block}</body>")

    # 7. Save the final HTML file
    map_path = os.path.join(HOSTING_PUBLIC_PATH, HTML_FILENAME)
    with open(map_path, "w", encoding="utf-8") as f:
        f.write(final_html)
        
    print(f"\n✅ --- Map built and saved to {map_path} ---")

def deploy_to_firebase_hosting():
    """Runs the 'firebase deploy' command to upload the new HTML."""
    print("  > 🚀 Deploying to Firebase Hosting...")
    try:
        subprocess.run(["firebase", "deploy", "--only", "hosting"], 
                       cwd=PROJECT_ROOT_PATH, # Run from the project root
                       check=True, shell=True, capture_output=True, text=True)
        print("  > ✅ Deploy complete!")
        print(f"  > View your live map at: {HOSTING_URL}/{HTML_FILENAME}")
    except subprocess.CalledProcessError as e:
        print(f"  > ❌ CRITICAL ERROR: Could not deploy to Firebase.")
        print(f"  > STDERR: {e.stderr}")
    except Exception as e:
        print(f"  > ❌ CRITICAL ERROR: Could not deploy to Firebase: {e}")

if __name__ == "__main__":
    if download_animation_library():
        build_map_with_live_javascript()
        deploy_to_firebase_hosting() # Build and deploy!
    else:
        print("❌ Could not build map because animation library download failed.")