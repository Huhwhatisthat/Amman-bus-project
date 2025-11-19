import firebase_admin
from firebase_admin import credentials, firestore

SERVICE_KEY_PATH = r"D:\beaning\bean\serviceAccountKey.json"

try:
    cred = credentials.Certificate(SERVICE_KEY_PATH)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Connected to Firebase")
except Exception as e:
    print(f"❌ Error: {e}")
    exit()

def list_stops(direction):
    print(f"\n--- STOPS FOR DIRECTION {direction} ---")
    doc_ref = db.collection("static_route_data").document(f"route_99_dir_{direction}")
    doc = doc_ref.get()
    
    if not doc.exists:
        print("No data found. Run bus_tracker.py first!")
        return

    data = doc.to_dict()
    stops = data.get('busStopList', [])
    
    for stop in stops:
        # Print the ID and Name so you can copy them
        print(f"ID: {stop['stopId']} | Name: {stop['stopName']}")

if __name__ == "__main__":
    list_stops(0) # To Museum
    list_stops(1) # To Swaileh