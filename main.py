import time
import random
import datetime
import os

# Import our new modules
import config
import api_client
import firebase_manager
import html_generator

if __name__ == "__main__":
    if not os.path.exists(config.HISTORICAL_DATA_PATH): os.makedirs(config.HISTORICAL_DATA_PATH)
    
    print("--- 🚌 BusPal Modular v1.0: Started! ---")
    firebase_manager.append_status_log(f"\n--- STARTED MODULAR v1.0 at {datetime.datetime.now().isoformat()} ---")
    
    consecutive_errors = 0
    total_ping_count = 0
    ping_streak = 0
    
    while True:
        now = datetime.datetime.now()
        is_active = config.ACTIVE_HOUR_START <= now.hour or now.hour < config.ACTIVE_HOUR_END
        
        print(f"\n--- Fetching ({now.strftime('%H:%M:%S')}) ---")
        
        api_success = False
        total_buses = 0
        all_buses_csv = []
        
        # 1. FETCH DATA
        for route in config.ROUTES_TO_TRACK:
            for d in [0, 1]:
                data = api_client.get_full_route_data(route, d)
                if data:
                    api_success = True
                    buses = data.get('busList', [])
                    
                    if buses:
                        print(f"  > Route {route} Dir {d}: {len(buses)} buses.")
                        # 2. SAVE LIVE DATA
                        if is_active: 
                            total_buses += firebase_manager.save_live_data(buses, route, d)
                        
                        for b in buses: 
                            b['direction'] = d
                            b['route'] = route
                        all_buses_csv.extend(buses)
                    
                    # 3. SAVE STATIC DATA
                    if is_active and data.get('pointList'): 
                        firebase_manager.save_static_data(data, route, d)

        # 4. HANDLE RESULTS
        if api_success:
            consecutive_errors = 0
            total_ping_count += 1
            ping_streak += 1
            
            # Save CSV
            firebase_manager.save_historical_csv(all_buses_csv, now, not is_active)
            
            summary = f"Saved {total_buses} buses. Streak: {ping_streak}."
            print(f"  > {summary}")
            
            if ping_streak % 10 == 0: 
                firebase_manager.append_status_log(f"{now.isoformat()} - {summary}")
            
            # 5. GENERATE & DEPLOY
            if html_generator.generate_html():
                if total_ping_count % 5 == 0: 
                    html_generator.deploy()
        else:
            consecutive_errors += 1
            print(f"  > ❌ API Error. Strike {consecutive_errors}")
            ping_streak = 0
        
        if consecutive_errors >= 5: break
        
        # Sleep
        sleep_duration = random.uniform(30, 45)
        print(f"Waiting {sleep_duration:.1f}s...")
        time.sleep(sleep_duration)