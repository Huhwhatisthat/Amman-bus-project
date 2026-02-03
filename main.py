import time
import random
import datetime
import os
import json
from haversine import haversine, Unit

import config
import api_client
import firebase_manager
import html_generator
import map_generator

# The registry now stores coords, timestamps, velocity, bearing, and path_index
BUS_REGISTRY = {} 

def get_bus_status(bus_id, current_coord, path_points, current_bearing):
    """
    Calculates movement status, velocity, and snaps the bus to the route path.
    """
    now_ts = time.time()
    
    # Find where the bus is on the official road map
    current_path_idx = html_generator.find_closest_point(current_coord, path_points)
    
    if bus_id not in BUS_REGISTRY:
        BUS_REGISTRY[bus_id] = {
            'coord': current_coord,
            'time': now_ts,
            'velocity': 0,
            'bearing': current_bearing,
            'path_idx': current_path_idx
        }
        return "🆕 NEW", 0.0, 0.0, current_path_idx, 0

    prev_data = BUS_REGISTRY[bus_id]
    dist_moved = haversine(prev_data['coord'], current_coord, unit=Unit.METERS)
    time_diff = now_ts - prev_data['time']
    velocity = dist_moved / time_diff if time_diff > 0 else 0
    
    # Calculate how many points along the road the bus advanced
    points_advanced = current_path_idx - prev_data['path_idx']
    
    # Update registry
    BUS_REGISTRY[bus_id] = {
        'coord': current_coord,
        'time': now_ts,
        'velocity': velocity,
        'bearing': current_bearing,
        'path_idx': current_path_idx
    }

    # Boundary detection for terminal/parking
    is_at_extreme = current_path_idx < 5 or current_path_idx > (len(path_points) - 5)

    if dist_moved > 5:
        return "🟢 MOVING", dist_moved, velocity, current_path_idx, points_advanced
    else:
        if is_at_extreme: return "🛑 PARKED (EXTREME)", dist_moved, 0.0, current_path_idx, 0
        return "🟡 STOPPED (BOARDING?)", dist_moved, 0.0, current_path_idx, 0

if __name__ == "__main__":
    if not os.path.exists(config.HISTORICAL_DATA_PATH): 
        os.makedirs(config.HISTORICAL_DATA_PATH)
    
    print("--- 🚌 BusPal v1.7: Path-Aware Interpolation Build ---")
    consecutive_stopped_cycles = 0
    
    while True:
        now = datetime.datetime.now()
        timestamp = now.strftime('%H:%M:%S')
        all_buses_data = []
        moving_count = 0
        api_success = False

        for route in config.ROUTES_TO_TRACK:
            for d in [0, 1]:
                data = api_client.get_full_route_data(route, d)
                if data:
                    api_success = True
                    buses = data.get('busList', [])
                    path_points = data.get('pointList', [])
                    
                    print(f"\n[{timestamp}] --- {route} Dir {d} | {len(buses)} Buses Found ---")

                    for b in buses:
                        b.pop('load', None) 
                        
                        # UPDATED: Now returns path_idx and points_advanced
                        status, delta, vel, p_idx, p_adv = get_bus_status(
                            b['busId'], 
                            (float(b['lat']), float(b['lng'])), 
                            path_points, 
                            b.get('bearing')
                        )
                        
                        if "MOVING" in status: moving_count += 1
                        
                        b.update({
                            'status': status,
                            'velocity': vel,
                            'direction': d,
                            'route': route,
                            'path_idx': p_idx
                        })
                        all_buses_data.append(b)
                        
                        kmh = vel * 3.6
                        # Verification Log: Shows progress along the road path
                        progress = f"Pt:{p_idx:3} (+{p_adv:2})"
                        print(f"  > {route} | Bus {b['busId']:8} | {status:20} | {kmh:4.1f} km/h | {progress}")

        if api_success:
            consecutive_stopped_cycles = (consecutive_stopped_cycles + 1) if moving_count == 0 else 0
            is_night_mode = consecutive_stopped_cycles >= config.STRIKES_UNTIL_NIGHT
            
            firebase_manager.save_historical_csv(all_buses_data, now, is_night_mode)

            if config.FORCE_CLOUD_UPDATE and not is_night_mode:
                firebase_manager.save_live_data(all_buses_data, "all_active", 0)
                
                json_path = os.path.join(config.HOSTING_PUBLIC_PATH, "all_active.json")
                with open(json_path, "w") as f:
                    json.dump(all_buses_data, f)

                map_generator.generate_map_html(all_buses_data)
                if html_generator.generate_html():
                    html_generator.deploy()
            
            mode_tag = "🌙 NIGHT" if is_night_mode else "☀️ DAY"
            print(f"\n[{timestamp}] {mode_tag} | Moving: {moving_count} | Cycles Stopped: {consecutive_stopped_cycles}/{config.STRIKES_UNTIL_NIGHT}")

        time.sleep(config.NIGHT_MODE_PING_INTERVAL if is_night_mode else random.uniform(config.PING_DELAY_MIN, config.PING_DELAY_MAX))