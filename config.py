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
ROUTES_TO_TRACK = ["99"]  # Reduced to one route for density

# --- API HEADERS ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'Referer': 'https://online.ammanbus.jo/',
    'Origin': 'https://online.ammanbus.jo'
}

# --- STOP CONFIGURATION ---
STOPS_TO_MONITOR = [
    {"name": "Mahmoud Alkiswani (Dir 0)", "stopId": "10620", "direction": 0, "route": "99"},
    {"name": "Agri. College (Dir 0)", "stopId": "10618", "direction": 0, "route": "99"},
    {"name": "Uni. of Jordan (Dir 0)", "stopId": "10617", "direction": 0, "route": "99"},
    {"name": "J.U. Hospital (Dir 0)", "stopId": "10619", "direction": 0, "route": "99"}
]
        
# --- STRESS TEST SETTINGS ---
# Lowering this will make pings more frequent
PING_DELAY_MIN = 30  # Seconds
PING_DELAY_MAX = 40  # Seconds

# How often to push the new data to the website (previously every 5 pings)
DEPLOY_EVERY_X_PINGS = 5