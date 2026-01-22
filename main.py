import time
import random
import datetime
import os
from haversine import haversine, Unit

import config
import api_client
import firebase_manager
import html_generator

# This remembers buses across loop cycles
BUS_REGISTRY = {} 

def get_bus_status(bus_id, current_coord, path_points):
    """
    Logic to determine if a bus is Moving, Boarding, or Parked.
    """
    if bus_id not in BUS_REGISTRY:
        BUS_REGISTRY[bus_id] = current_coord
        return "🆕 NEW", 0

    last_coord = BUS_REGISTRY[bus_id]
    dist_moved = haversine(last_coord, current_coord, unit=Unit.METERS)
    BUS_REGISTRY[bus_id] = current_coord # Update registry for next time

    # Determine Path Position
    # We use the html_generator's math to see where it is on the line
    idx = html_generator.find_closest_point(current_coord, path_points)
    is_at_extreme = idx < 5 or idx > (len(path_points) - 5)

    if dist_moved > 5:
        return "🟢 MOVING", dist_moved
    else:
        if is_at_extreme:
            return "🛑 PARKED (EXTREME)", dist_moved
        return "🟡 STOPPED (BOARDING?)", dist_moved

if __name__ == "__main__":
    if not os.path.exists(config.HISTORICAL_DATA_PATH): os.makedirs(config.HISTORICAL_DATA_PATH)
    
    print("--- 🚌 BusPal Dev Build: Movement Tracking v1.0 ---")
    
    while True:
        now = datetime.datetime.now()
        api_success = False
        all_buses_csv_data = []
        
        # We only track Route 99, Dir 0 as requested
        data = api_client.get_full_route_data("99", 0)
        
        if data:
            api_success = True
            buses = data.get('busList', [])
            path_points = data.get('pointList', [])
            
            print(f"\n--- Snapshot: {now.strftime('%H:%M:%S')} | {len(buses)} Buses Found ---")

            for b in buses:
                b_id = b.get('busId')
                curr_loc = (float(b['lat']), float(b['lng']))
                
                # GET MOVEMENT STATUS
                status, diff = get_bus_status(b_id, curr_loc, path_points)
                
                print(f"  > Bus {b_id} | {status} | Delta: {diff:.1f}m")
                if "MOVING" in status:
                    print(f"    Current: {curr_loc}")

                # Prepare for storage
                b['direction'] = 0
                b['route'] = "99"
                all_buses_csv_data.extend(buses)
                
            firebase_manager.save_live_data(buses, "99", 0)
            firebase_manager.save_static_data(data, "99", 0)

        if api_success:
            firebase_manager.save_historical_csv(all_buses_csv_data, now, False)
            if html_generator.generate_html():
                html_generator.deploy()
        else:
            print("  > ⚠️ API Error.")

        sleep_duration = random.uniform(config.PING_DELAY_MIN, config.PING_DELAY_MAX)
        print(f"Waiting {sleep_duration:.1f}s...")
        time.sleep(sleep_duration)