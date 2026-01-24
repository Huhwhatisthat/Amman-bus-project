import os
import config
import json

def generate_map_html(buses):
    print(f"  > 🗺️ Generating Autonomous Map | {len(buses)} Buses")
    
    colors = {
        "99": ["#ff7777", "#990000"],
        "100": ["#7777ff", "#000099"],
        "98": ["#77ff77", "#009900"]
    }
    bus_json = json.dumps(buses)
    color_json = json.dumps(colors)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>BusPal National Dashboard</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background: #111; font-family: sans-serif; }}
            #map {{ height: 100vh; width: 100%; }}
            .sidebar {{
                position: absolute; top: 10px; right: 10px; z-index: 1000;
                background: rgba(0,0,0,0.9); color: white; padding: 12px; 
                border-radius: 8px; border: 1px solid #444; width: 160px;
            }}
            .bus-square {{
                width: 22px; height: 22px; border: 2px solid white;
                display: flex; align-items: center; justify-content: center;
                color: white; font-weight: bold; font-size: 10px; position: relative;
            }}
            .pointer {{
                position: absolute; top: -8px; width: 0; height: 0;
                border-left: 6px solid transparent; border-right: 6px solid transparent;
                border-bottom: 8px solid white;
            }}
            label {{ display: block; margin: 8px 0; font-size: 13px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <h4 style="margin:0 0 10px 0;">🛰️ Filter View</h4>
            <div id="controls"></div>
            <div id="status" style="font-size:10px; color:#0f0; margin-top:10px;">Syncing...</div>
        </div>
        <div id="map"></div>
        <script>
            var map = L.map('map').setView([32.00247, 35.87108], 13);
            L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png').addTo(map);

            var routeColors = {color_json};
            var markers = {{}};
            var visibility = {{ "98":true, "99":true, "100":true, "d0":true, "d1":true }};

            function updateBusIcon(busId, bearing, route, shade) {{
                return '<div id="cont-' + busId + '" style="transform: rotate(' + (bearing || 0) + 'deg); display: flex; flex-direction: column; align-items: center;">' +
                       '<div class="pointer"></div>' +
                       '<div class="bus-square" style="background: ' + shade + ';">' + route + '</div>' +
                       '</div>';
            }}

            function processBuses(busList) {{
                busList.forEach(function(bus) {{
                    if (bus.status === "🛑 PARKED (EXTREME)") {{
                        if (markers[bus.busId]) {{ map.removeLayer(markers[bus.busId]); delete markers[bus.busId]; }}
                        return;
                    }}
                    var shades = routeColors[bus.route] || ["#fff", "#888"];
                    var shade = (bus.direction == 1) ? shades[1] : shades[0];
                    
                    if (markers[bus.busId]) {{
                        markers[bus.busId].busData = bus; // Update data for interpolation
                        markers[bus.busId].setLatLng([bus.lat, bus.lng]);
                        document.getElementById("cont-" + bus.busId).parentElement.innerHTML = updateBusIcon(bus.busId, bus.bearing, bus.route, shade);
                    }} else {{
                        var marker = L.marker([bus.lat, bus.lng], {{
                            icon: L.divIcon({{ className: '', html: updateBusIcon(bus.busId, bus.bearing, bus.route, shade), iconSize: [30, 30] }})
                        }}).addTo(map);
                        marker.bindPopup("<b>Bus: " + bus.busId + "</b>");
                        marker.busData = bus;
                        marker.lastUpdate = Date.now();
                        markers[bus.busId] = marker;
                    }}
                }});
            }}

            // Initial Load
            processBuses({bus_json});

            // --- AUTO-PULL DATA ---
            function refreshData() {{
                fetch('all_active.json?' + new Date().getTime()) // Prevent caching
                    .then(response => response.json())
                    .then(data => {{
                        processBuses(data);
                        document.getElementById('status').innerHTML = "Last Sync: " + new Date().toLocaleTimeString();
                    }}).catch(err => console.log("Waiting for new data..."));
            }}
            setInterval(refreshData, 10000);

            // --- INTERPOLATION ENGINE ---
            function animate() {{
                var now = Date.now();
                Object.keys(markers).forEach(function(id) {{
                    var m = markers[id];
                    var bus = m.busData;
                    var isVisible = visibility[bus.route] && visibility["d" + bus.direction];
                    
                    if (!isVisible) {{ if (map.hasLayer(m)) map.removeLayer(m); return; }}
                    else {{ if (!map.hasLayer(m)) map.addLayer(m); }}

                    if (bus.status === "🟢 MOVING" && bus.velocity > 0) {{
                        var dt = (now - m.lastUpdate) / 1000;
                        m.lastUpdate = now;
                        var moveM = bus.velocity * dt;
                        var rad = ((bus.bearing || 0) * Math.PI) / 180;
                        bus.lat += (moveM * Math.cos(rad)) / 111000;
                        bus.lng += (moveM * Math.sin(rad)) / (111000 * Math.cos(bus.lat * Math.PI / 180));
                        m.setLatLng([bus.lat, bus.lng]);
                    }}
                }});
                requestAnimationFrame(animate);
            }}
            animate();

            // Build Toggles
            var ctrl = document.getElementById('controls');
            ["99","100","98","d0","d1"].forEach(function(key) {{
                var label = document.createElement('label');
                var text = key.startsWith('d') ? "Direction " + key[1] : "Route " + key;
                label.innerHTML = '<input type="checkbox" checked onchange="visibility[\\'' + key + '\\']=this.checked"> ' + text;
                ctrl.appendChild(label);
            }});
        </script>
    </body>
    </html>
    """
    with open(os.path.join(config.HOSTING_PUBLIC_PATH, "map.html"), "w", encoding="utf-8") as f:
        f.write(html_content)