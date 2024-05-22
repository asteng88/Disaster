import pandas as pd
import folium, webbrowser, os, schedule, sys, time, math
from gdacs.api import GDACSAPIReader

def load_companies_from_csv(file_path):
    """Load company data from a CSV file."""
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

def check_disaster_vicinity(company_lat, company_lon, disasters_data):
    """Check if a company is within 241 kilometers of any disaster."""
    in_jeopardy = False
    for disaster in disasters_data:
        disaster_lat, disaster_lon = disaster['coordinates']
        distance = haversine(company_lat, company_lon, disaster_lat, disaster_lon)
        if distance <= 241:
            print(f"\033[91mCompany at ({company_lat}, {company_lon}) is within {distance:.2f} km of disaster at ({disaster_lat}, {disaster_lon})\033[0m")
            in_jeopardy = True
        else:
            print(f"Company at ({company_lat}, {company_lon}) is {distance:.2f} km away from disaster at ({disaster_lat}, {disaster_lon})")
    return in_jeopardy

def create_map_from_companies(companies_df, disasters_data, include_disasters=False):
    """Create a map showing companies and optionally disasters."""
    if companies_df.empty:
        print("No company data available.")
        return None
    
    # Set initial location to Indianapolis, Indiana
    initial_location = [39.7684, -86.1581]  
    company_map = folium.Map(location=initial_location, zoom_start=2)

    for _, row in companies_df.iterrows():
        in_jeopardy = check_disaster_vicinity(row['Latitude'], row['Longitude'], disasters_data)
        color = 'red' if in_jeopardy else 'blue'
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=f"{row['Company_Name']}{' - In Jeopardy!' if in_jeopardy else ''}",
            icon=folium.Icon(color=color)
        ).add_to(company_map)

    if include_disasters:
        for disaster in disasters_data:
            folium.Marker(
                location=disaster['coordinates'][::-1],  # Reverse coordinates here
                popup=f"Disaster: {disaster['name']} ({disaster['disaster_type']})",
                icon=folium.Icon(color='orange')
            ).add_to(company_map)

            folium.Circle(
                location=disaster['coordinates'][::-1],  # Reverse coordinates here
                radius=241000,  # 241 km in meters
                color='orange',
                fill=True,
                fill_opacity=0.3
            ).add_to(company_map)

    map_path = 'updated_all_companies_map.html'
    company_map.save(map_path)
    return map_path

def extract_disaster_info(disasters):
    """Extract relevant information from disaster data."""
    disaster_info = []
    if 'features' not in disasters:
        raise ValueError("Disaster data format not as expected. Missing 'features' key.")
    for feature in disasters['features']:
        try:
            properties = feature['properties']
            name = properties.get('name', 'No Name Available')
            disaster_type = properties.get('eventtype', 'Unknown')
            geometry = feature['geometry']
            if geometry and geometry['type'] == 'Point':  # Ensure it's a point geometry
                coordinates = geometry.get('coordinates', [None, None])
                print("Coordinates:", coordinates)  # Check coordinates
                disaster_info.append({
                    'name': name,
                    'disaster_type': disaster_type,
                    'coordinates': coordinates
                })
        except KeyError as e:
            print(f"Error extracting disaster info for feature: {feature}. Missing key: {e}")
    return disaster_info

def fetch_and_update_map(csv_path, include_disasters=False):
    """Fetch the latest disaster data and update the map."""
    try:
        client = GDACSAPIReader()
        disaster_data = client.latest_events()
        disaster_data = vars(disaster_data)
        disaster_info = extract_disaster_info(disaster_data)
        companies_df = load_companies_from_csv(csv_path)
        map_path = create_map_from_companies(companies_df, disaster_info, include_disasters)
        print("Map updated with the latest disaster data. See below\n")
        print(disaster_info)  # Print the entire disaster_info
        webbrowser.open('file://' + os.path.realpath(map_path), new=0)  # Open the map in the browser
    except Exception as e:
        print(f"Error during fetching or processing: {e}")
        import traceback
        traceback.print_exc()  # Print the traceback to get more details about the error

# Initial display of the map
fetch_and_update_map('companies.csv', include_disasters=True)

# Automatically update the map every hour
schedule.every().hour.do(fetch_and_update_map, csv_path='companies.csv', include_disasters=True)

while True:
    schedule.run_pending()
    for i in range(7200, 0, -1):  # 3600 seconds = 1 hour
        sys.stdout.write("\rScheduler started. Next update in {:02d}:{:02d} minutes".format(i // 60, i % 60))
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\n")
