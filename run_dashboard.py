import time
import datetime
import html_generator
import map_generator
import firebase_manager

print("--- 👻 BusPal Ghost Engine: Predicting Amman Movement ---")

def run_prediction_cycle():
    now = datetime.datetime.now()
    timestamp = now.strftime('%H:%M:%S')
    
    # 1. Fetch latest "all_active" data from cloud
    all_buses = firebase_manager.get_live_data_full("all_active", 0)
    
    if all_buses:
        bus_list = all_buses.get('buses', [])
        print(f"[{timestamp}] Refreshing Views | {len(bus_list)} Buses tracked.")

        # 2. Update Map and ETA List
        map_generator.generate_map_html(bus_list)
        if html_generator.generate_html():
            # 3. Deploy
            html_generator.deploy()
    else:
        print(f"[{timestamp}] ⚠️ No active data in Firebase yet.")

if __name__ == "__main__":
    GHOST_REFRESH_RATE = 20 
    while True:
        run_prediction_cycle()
        time.sleep(GHOST_REFRESH_RATE)