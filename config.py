import os

# --- PATHS ---
# KEEP THESE EXACTLY AS THEY WERE ON YOUR PC
SERVICE_KEY_PATH = r"D:\beaning\bean\serviceAccountKey.json"
PROJECT_ROOT_PATH = r"C:\Users\user\Desktop\Amman-bus-project" 
HISTORICAL_DATA_PATH = os.path.join(PROJECT_ROOT_PATH, "data")
HOSTING_PUBLIC_PATH = os.path.join(PROJECT_ROOT_PATH, "public") 

# --- SETTINGS ---
USER_LOCATION = (32.00247, 35.87108) 
AVG_WALK_SPEED_MPS = 1.3 
AVG_BUS_SPEED_MPS = 8.3  
ACTIVE_HOUR_START = 6
ACTIVE_HOUR_END = 0 

ROUTES_TO_TRACK = ["98", "99", "100"]

# --- API HEADERS ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'Referer': 'https://online.ammanbus.jo/',
    'Origin': 'https://online.ammanbus.jo'
}

# --- STOP CONFIGURATION ---
STOPS_TO_MONITOR = []
_target_stops = [
    {"id": "10620", "name": "Mahmoud Alkiswani"},
    {"id": "10618", "name": "Agri. College"},
    {"id": "10617", "name": "Uni. of Jordan"},
    {"id": "10619", "name": "J.U. Hospital"}
]

for route in ROUTES_TO_TRACK:
    for stop in _target_stops:
        STOPS_TO_MONITOR.append({
            "name": f"{stop['name']} (Dir 0)",
            "stopId": stop['id'],
            "direction": 0,
            "route": route
        })
        STOPS_TO_MONITOR.append({
            "name": f"{stop['name']} (Dir 1)",
            "stopId": stop['id'],
            "direction": 1,
            "route": route
        })