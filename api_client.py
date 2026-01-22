import requests
import config

def get_full_route_data(route_code, direction):
    url = f"https://mobile.ammanbus.jo/rl1//web/pathInfo?region=116&lang=en&authType=4&direction={direction}&displayRouteCode={route_code}&resultType=111111"
    try:
        response = requests.get(url, headers=config.HEADERS, timeout=10)
        response.raise_for_status() 
        data = response.json()
        # Return the path list if valid, else None
        return data['pathList'][0] if data.get('pathList') else None
    except: 
        return None