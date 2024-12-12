import pandas as pd
import folium
import webbrowser
import os
import math
import time
import json
from gdacs.api import GDACSAPIReader
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs
import signal

def load_locations_from_csv(file_path):
    """Load location data from a CSV file."""
    return pd.read_csv(file_path)

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth."""
    R = 6378.1  # Earth radius in kilometers at the equator
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # Distance in kilometers

def check_disaster_vicinity(company_lat, company_lon, disasters_data, disaster_range):
    """Check if a company is within the specified range of any disaster."""
    for disaster in disasters_data:
        disaster_lat, disaster_lon = disaster['coordinates']
        distance = haversine(company_lat, company_lon, disaster_lat, disaster_lon)
        print(f"Checking location ({company_lat}, {company_lon}) against disaster at ({disaster_lat}, {disaster_lon}). Distance: {distance:.2f} km, Range: {disaster_range} km")
        if distance <= disaster_range:
            print(f"Location in jeopardy! Distance: {distance:.2f} km, Range: {disaster_range} km")
            return True
    return False

def create_map_from_locations(locations_df, disasters_data, include_disasters=False, disaster_range=241):
    """Create a map showing locations and optionally disasters."""
    if locations_df.empty:
        print("No location data available.")
        return None

    initial_location = [41.8719, 12.5674]  # Italy as the center of the map
    company_map = folium.Map(location=initial_location, zoom_start=2)

    for _, row in locations_df.iterrows():
        in_jeopardy = check_disaster_vicinity(row['Latitude'], row['Longitude'], disasters_data, disaster_range)
        color = 'red' if in_jeopardy else 'blue'
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=f"{row['Location_Name']}{' - In Jeopardy!' if in_jeopardy else ''}",
            icon=folium.Icon(color=color)
        ).add_to(company_map)

    if include_disasters:
        for disaster in disasters_data:
            folium.Marker(
                location=disaster['coordinates'][::-1],
                popup=f"Disaster: {disaster['name']} ({disaster['disaster_type']})",
                icon=folium.Icon(color='orange')
            ).add_to(company_map)

            folium.Circle(
                location=disaster['coordinates'][::-1],
                radius=disaster_range * 1000,  # Convert km to meters
                color='orange',
                fill=True,
                fill_opacity=0.3,
                id=f"disaster_circle_{disaster['name'].replace(' ', '_')}",  # Add an ID to the circle
                className='pulsating-circle'  # Add a class for styling
            ).add_to(company_map)

    # Add CSS for pulsating effect
    pulsating_css = """
    <style>
    @keyframes pulse {
        0% {
            stroke-opacity: 0.8;
            stroke-width: 1;
        }
        50% {
            stroke-opacity: 0.3;
            stroke-width: 3;
        }
        100% {
            stroke-opacity: 0.8;
            stroke-width: 1;
        }
    }
    .pulsating-circle {
        animation: pulse 2s ease-in-out infinite;
    }
    </style>
    """
    company_map.get_root().html.add_child(folium.Element(pulsating_css))

    # Add current settings to the map
    current_settings = f"""
    <script>
    var currentRefreshInterval = {get_refresh_interval()};
    var currentDisasterRange = {disaster_range};
    </script>
    """
    company_map.get_root().html.add_child(folium.Element(current_settings))

    # Add dropdowns for refresh rate and disaster range selection, and progress bar
    dropdowns_and_progress_html = """
    <div id="control-panel" style="position: absolute; top: 10px; right: 10px; z-index: 1000; background: rgba(255, 255, 255, 0.7); padding: 10px; border-radius: 5px;">
        <label for="refresh-rate">Refresh Rate:</label>
        <select id="refresh-rate">
            <option value="600">10 minutes</option>
            <option value="3600" selected>1 hour</option>
            <option value="21600">6 hours</option>
            <option value="43200">12 hours</option>
            <option value="86400">24 hours</option>
        </select>
        <br><br>
        <label for="disaster-range">Disaster Range (km):</label>
        <select id="disaster-range">
            <option value="241" selected>241 (Default)</option>
            <option value="300">300</option>
            <option value="400">400</option>
            <option value="500">500</option>
            <option value="600">600</option>
            <option value="700">700</option>
            <option value="800">800</option>
            <option value="900">900</option>
            <option value="1000">1000</option>
        </select>
    </div>
    <div id="progress-bar-container" style="position: fixed; bottom: 15px; left: 0; width: 100%; height: 10px; background-color: rgba(0, 0, 0, 0.1); z-index: 1000;">
        <div id="progress-bar" style="width: 0%; height: 100%; background-color: rgba(0, 255, 0, 0.5);"></div>
    </div>
    """
    company_map.get_root().html.add_child(folium.Element(dropdowns_and_progress_html))

    # Add JavaScript for refresh functionality, disaster range update, progress bar, and heartbeat
    refresh_script = """
    <script>
    var refreshInterval;
    var progressInterval;
    var startTime;
    var duration;

    function updateProgressBar() {
        var currentTime = new Date().getTime();
        var elapsedTime = currentTime - startTime;
        var progress = (elapsedTime / duration) * 100;
        document.getElementById('progress-bar').style.width = progress + '%';
        
        if (progress >= 100) {
            clearInterval(progressInterval);
        }
    }

    function setRefreshInterval() {
        clearInterval(refreshInterval);
        clearInterval(progressInterval);
        
        var refreshRate = document.getElementById('refresh-rate').value;
        duration = refreshRate * 1000;
        startTime = new Date().getTime();
        
        // Update the refresh_config.json file
        fetch('http://localhost:8000/update_refresh_rate?interval=' + refreshRate)
            .then(response => response.text())
            .then(data => console.log(data))
            .catch(error => console.error('Error:', error));

        refreshInterval = setInterval(function() {
            location.reload();
        }, duration);
        
        progressInterval = setInterval(updateProgressBar, 1000); // Update progress every second
        updateProgressBar(); // Initial update
    }

    function updateDisasterRange() {
        var disasterRange = document.getElementById('disaster-range').value;
        fetch('http://localhost:8000/update_disaster_range?range=' + disasterRange)
            .then(response => response.text())
            .then(data => {
                console.log(data);
                location.reload();  // Reload the page to reflect the changes
            })
            .catch(error => console.error('Error:', error));
    }

    function sendHeartbeat() {
        fetch('http://localhost:8000/heartbeat')
            .then(response => response.text())
            .catch(error => console.error('Error:', error));
    }

    // Send heartbeat every 5 seconds
    setInterval(sendHeartbeat, 5000);

    document.getElementById('refresh-rate').addEventListener('change', setRefreshInterval);
    document.getElementById('disaster-range').addEventListener('change', updateDisasterRange);
    setRefreshInterval();
    </script>
    """
    company_map.get_root().html.add_child(folium.Element(refresh_script))

    map_path = 'updated_all_locations_map.html'
    company_map.save(map_path)
    return map_path

def extract_disaster_info(disasters):
    """Extract relevant information from disaster data."""
    disaster_info = []
    for feature in disasters['features']:
        properties = feature['properties']
        name = properties.get('name', 'No Name Available')
        disaster_type = properties.get('eventtype', 'Unknown')
        geometry = feature['geometry']
        coordinates = geometry.get('coordinates', [None, None])
        disaster_info.append({
            'name': name,
            'disaster_type': disaster_type,
            'coordinates': coordinates
        })
    return disaster_info

def fetch_and_update_map(csv_path, include_disasters=True):
    """Fetch the latest disaster data and update the map."""
    try:
        client = GDACSAPIReader()
        disaster_data = client.latest_events()
        disaster_data = vars(disaster_data)
        disaster_info = extract_disaster_info(disaster_data)
        locations_df = load_locations_from_csv(csv_path)
        disaster_range = get_disaster_range()  # Get the current disaster range
        map_path = create_map_from_locations(locations_df, disaster_info, include_disasters, disaster_range)
        print(f"Map updated with the latest disaster data. Disaster range: {disaster_range} km")
        return map_path
    except Exception as e:
        print(f"Error during fetching or processing: {e}")
        return None

def get_refresh_interval():
    with open('refresh_config.json', 'r') as f:
        config = json.load(f)
    return config['refresh_interval']

def update_refresh_interval(new_interval):
    with open('refresh_config.json', 'r') as f:
        config = json.load(f)
    config['refresh_interval'] = new_interval
    with open('refresh_config.json', 'w') as f:
        json.dump(config, f)

def get_disaster_range():
    with open('refresh_config.json', 'r') as f:
        config = json.load(f)
    return config.get('disaster_range', 241)  # Default to 241 if not set

def update_disaster_range(new_range):
    with open('refresh_config.json', 'r') as f:
        config = json.load(f)
    config['disaster_range'] = new_range
    with open('refresh_config.json', 'w') as f:
        json.dump(config, f)

def update_map_periodically(csv_path, include_disasters=True):
    while True:
        interval = get_refresh_interval()
        map_path = fetch_and_update_map(csv_path, include_disasters)
        print(f"Map updated at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(interval)

class CustomHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        global last_heartbeat  # Add this line to access the global variable
        if self.path.startswith('/update_refresh_rate'):
            query = parse_qs(self.path.split('?')[1])
            new_interval = int(query['interval'][0])
            update_refresh_interval(new_interval)
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b"Refresh interval updated")
        elif self.path.startswith('/update_disaster_range'):
            query = parse_qs(self.path.split('?')[1])
            new_range = int(query['range'][0])
            update_disaster_range(new_range)
            fetch_and_update_map('locations.csv')  # Update the map with the new range
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b"Disaster range updated and map refreshed")
        elif self.path == '/heartbeat':
            last_heartbeat = time.time()  # Update the last heartbeat time
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b"Heartbeat received")
        else:
            super().do_GET()

def signal_handler(signum, frame):
    print("Received signal to terminate. Shutting down...")
    os._exit(0)

if __name__ == '__main__':
    csv_path = 'locations.csv'
    initial_map_path = fetch_and_update_map(csv_path, include_disasters=True)
    
    if initial_map_path:
        webbrowser.open('file://' + os.path.realpath(initial_map_path), new=2)
        
        # Start a background thread to update the map periodically
        update_thread = threading.Thread(target=update_map_periodically, args=(csv_path,))
        update_thread.daemon = True
        update_thread.start()
        
        print("Map is now open in your web browser. It will refresh automatically based on the selected interval.")
        print("The map file will be updated based on the selected interval with new disaster data.")
        print("You can keep this script running to continue updating the map file.")
        
        # Set up signal handler
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Start a simple HTTP server to handle refresh rate updates and heartbeats
        server = HTTPServer(('localhost', 8000), CustomHandler)
        print("Starting server at http://localhost:8000")
        
        # Set up a timer to check for heartbeats
        global last_heartbeat
        last_heartbeat = time.time()
        
        while True:
            server.handle_request()
            if time.time() - last_heartbeat > 30:  # Increase timeout to 30 seconds
                print("No heartbeat received. Assuming browser window closed. Shutting down...")
                break
        
        os._exit(0)