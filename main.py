import time
import random
import datetime
import os
from haversine import haversine, Unit

import config
import api_client
import firebase_manager
import html_generator

# The registry now stores coords, timestamps, and velocity
BUS_REGISTRY = {} 

def get_bus_status(bus_id, current_coord, path_points):
    """
    Calculates movement status and velocity for interpolation.
    """
    now_ts = time.time()
    
    if bus_id not in BUS_REGISTRY:
        BUS_REGISTRY[bus_id] = {
            'coord': current_coord,
            'time': now_ts,
            'velocity': 0
        }
        return "🆕 NEW", 0, 0

    prev_data = BUS_REGISTRY[bus_id]
    last_coord = prev_data['coord']
    last_time = prev_data['time']
    
    # Calculate physical changes
    dist_moved = haversine(last_coord, current_coord, unit=Unit.METERS)
    time_diff = now_ts - last_time
    
    # Calculate Velocity (m/s)
    velocity = dist_moved / time_diff if time_diff > 0 else 0
    
    # Update registry for the next cycle
    BUS_REGISTRY[bus_id] = {
        'coord': current_coord,
        'time': now_ts,
        'velocity': velocity
    }

    # Determine state based on 5-meter threshold
    idx = html_generator.find_closest_point(current_coord, path_points)
    is_at_extreme = idx < 5 or idx > (len(path_points) - 5)

    if dist_moved > 5:
        return "🟢 MOVING", dist_moved, velocity
    else:
        if is_at_extreme:
            return "🛑 PARKED (EXTREME)", dist_moved, 0
        return "🟡 STOPPED (BOARDING?)", dist_moved, 0

if __name__ == "__main__":
    if not os.path.exists(config.HISTORICAL_DATA_PATH): os.makedirs(config.HISTORICAL_DATA_PATH)
    
    print("--- 🚌 BusPal Dev Build: Velocity Tracking v1.2 ---")
    
    while True:
        now = datetime.datetime.now()
        api_success = False
        all_buses_data = []
        
        data = api_client.get_full_route_data("99", 0)
        
        if data:
            api_success = True
            buses = data.get('busList', [])
            path_points = data.get('pointList', [])
            
            print(f"\n--- Snapshot: {now.strftime('%H:%M:%S')} | {len(buses)} Buses ---")

            for b in buses:
                b_id = b.get('busId')
                curr_loc = (float(b['lat']), float(b['lng']))
                
                # Get Status and Velocity
                status, diff, vel = get_bus_status(b_id, curr_loc, path_points)
                b['status'] = status
                b['velocity'] = vel # We'll log this too
                
                print(f"  > Bus {b_id} | {status} | {vel:.1f} m/s | Δ:{diff:.1f}m")

                b['direction'] = 0
                b['route'] = "99"
                all_buses_data.append(b)
                
            firebase_manager.save_live_data(all_buses_data, "99", 0)
            firebase_manager.save_static_data(data, "99", 0)

        if api_success:
            firebase_manager.save_historical_csv(all_buses_data, now, False)
            if html_generator.generate_html():
                html_generator.deploy()
        
        sleep_duration = random.uniform(config.PING_DELAY_MIN, config.PING_DELAY_MAX)
        print(f"Waiting {sleep_duration:.1f}s...")
        time.sleep(sleep_duration)