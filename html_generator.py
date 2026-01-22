import os
import datetime
import subprocess
from haversine import haversine, Unit
import config
import firebase_manager

# --- MATH UTILS ---
def find_closest_point(bus_coord, path_points):
    closest_dist = float('inf')
    closest_index = -1
    for i, point in enumerate(path_points):
        point_coord = (float(point['lat']), float(point['lng']))
        dist = haversine(bus_coord, point_coord)
        if dist < closest_dist:
            closest_dist = dist
            closest_index = i
    return closest_index

def calculate_path_dist(start_index, end_index, path_points):
    total_dist = 0
    if start_index == -1 or end_index == -1 or start_index >= end_index:
        return 0
    for i in range(start_index, end_index):
        p1 = (float(path_points[i]['lat']), float(path_points[i]['lng']))
        p2 = (float(path_points[i+1]['lat']), float(path_points[i+1]['lng']))
        total_dist += haversine(p1, p2, unit=Unit.METERS)
    return total_dist

# --- HTML GENERATION ---
def generate_html():
    print("  > 🚌 Generating HTML...")
    html_cards = []
    
    for stop_config in config.STOPS_TO_MONITOR:
        route = stop_config['route']
        direction = stop_config['direction']
        target_stop_id = stop_config['stopId']
        
        static_data = firebase_manager.get_static_data(route, direction)
        live_buses = firebase_manager.get_live_data(route, direction)
        
        if not static_data: continue
            
        target_stop = next((s for s in static_data.get('busStopList', []) if s['stopId'] == target_stop_id), None)
        if not target_stop: continue 

        stop_coord = (float(target_stop['lat']), float(target_stop['lng']))
        stop_path_index = find_closest_point(stop_coord, static_data['pointList'])
        
        walk_dist_m = haversine(config.USER_LOCATION, stop_coord, unit=Unit.METERS)
        walk_time_min = (walk_dist_m / config.AVG_WALK_SPEED_MPS) / 60
        
        upcoming_buses = [] 
        
        for bus in live_buses:
            bus_coord = (float(bus['lat']), float(bus['lng']))
            bus_path_index = find_closest_point(bus_coord, static_data['pointList'])
            
            if bus_path_index < stop_path_index:
                dist_m = calculate_path_dist(bus_path_index, stop_path_index, static_data['pointList'])
                bus_travel_time = (dist_m / config.AVG_BUS_SPEED_MPS) / 60
                leave_in_min = bus_travel_time - walk_time_min
                
                upcoming_buses.append({'leave_in': leave_in_min, 'load': bus.get('load', '?')})
        
        upcoming_buses.sort(key=lambda x: x['leave_in'])
        
        # --- DISPLAY LOGIC ---
        main_eta = "--"
        sub_text = "No Bus"
        next_bus_text = "Next: --"
        
        if upcoming_buses:
            first_bus = upcoming_buses[0]
            val = first_bus['leave_in']
            
            if val > 1:
                main_eta = str(int(round(val)))
                sub_text = "min to leave"
            elif val > 0:
                main_eta = "<1"
                sub_text = "Run!"
            else:
                main_eta = "NOW"
                sub_text = f"({abs(int(val))} min ago)"
                
            if len(upcoming_buses) > 1:
                second_bus = upcoming_buses[1]
                val_2 = int(round(second_bus['leave_in']))
                load_2 = second_bus['load']
                next_bus_text = f"Next: {val_2} min (L:{load_2})"

        html_cards.append(f"""
            <div class="stop-card">
                <div class="card-header">
                    <span class="route-badge">{route}</span>
                    <span class="stop-name">{stop_config['name']}</span>
                </div>
                <div class="eta-container">
                    <div class="eta-main">{main_eta}</div>
                    <div class="eta-sub">{sub_text}</div>
                </div>
                <div class="footer">{next_bus_text}</div>
            </div>
        """)
    
    # Simple CSS Template (Condensed)
    html_template = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta http-equiv="refresh" content="30"><title>Bus Aunty</title><style>body {{ background-color: #ffffff; font-family: Helvetica, Arial, sans-serif; margin: 0; padding: 10px; min-height: 100vh; box-sizing: border-box; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; align-content: start; }} .stop-card {{ background-color: #f4f4f4; border: 2px solid #000; border-radius: 8px; display: flex; flex-direction: column; padding: 10px; min-height: 140px; }} .card-header {{ display: flex; justify-content: flex-start; align-items: center; gap: 8px; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-bottom: 5px; }} .stop-name {{ font-size: 1em; font-weight: bold; color: #333; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }} .route-badge {{ background: #000; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 1.1em; }} .eta-container {{ flex-grow: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; }} .eta-main {{ font-size: 3.5em; font-weight: 800; line-height: 1; }} .eta-sub {{ font-size: 0.9em; color: #555; margin-top: 2px; font-weight: bold; }} .footer {{ margin-top: auto; border-top: 1px solid #ccc; padding-top: 5px; text-align: center; font-size: 0.8em; color: #444; }} .timestamp {{ position: fixed; bottom: 5px; right: 5px; font-size: 0.7em; color: #aaa; background: rgba(255,255,255,0.8); padding: 2px; }}</style></head><body>{''.join(html_cards)}<div class="timestamp">Updated: {datetime.datetime.now().strftime('%I:%M %p')}</div></body></html>"""
    
    try:
        html_file_path = os.path.join(config.HOSTING_PUBLIC_PATH, "bus_aunty.html")
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        return True
    except Exception as e:
        print(f"  > ❌ HTML Error: {e}")
        return False

def deploy():
    print("  > 🚀 Deploying...")
    try:
        subprocess.run(["firebase", "deploy", "--only", "hosting"], 
                       cwd=config.PROJECT_ROOT_PATH, check=True, shell=True, capture_output=True)
        print("  > ✅ Deployed!")
    except: print("  > ❌ Deploy Failed")