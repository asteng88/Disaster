from cgitb import text
import pandas as pd
import folium, webbrowser, os, schedule, pyautogui, time
from gdacs.api import GDACSAPIReader

def load_companies_from_csv(file_path):
    return pd.read_csv(file_path)

def check_disaster_vicinity(company_lat, company_lon, disasters_data):
    for disaster in disasters_data:
        disaster_lat, disaster_lon = disaster['coordinates']
        if abs(disaster_lat - company_lat) < 0.5 and abs(disaster_lon - company_lon) < 0.5:
            return True
    return False

def create_map_from_companies(companies_df, disasters_data, include_disasters=False):
    if companies_df.empty:
        print("No company data available.")
        return None
    initial_location = [companies_df.iloc[0]['Latitude'], companies_df.iloc[0]['Longitude']]
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
                location=disaster['coordinates'][::-1],  # Reverse the coordinates if necessary
                popup=f"Disaster: {disaster['name']} ({disaster['disaster_type']})",
                icon=folium.Icon(color='orange')
            ).add_to(company_map)

    company_map.save('updated_all_companies_map.html')
    return company_map

def extract_disaster_info(disasters):
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

def fetch_and_update_map(csv_path, include_disasters=False):
    try:
        client = GDACSAPIReader()
        disaster_data = client.latest_events()
        disaster_data = vars(disaster_data)
        disaster_info = extract_disaster_info(disaster_data)
        companies_df = load_companies_from_csv(csv_path)
        create_map_from_companies(companies_df, disaster_info, include_disasters)
        print("Map updated with the latest disaster data.")
        pyautogui.hotkey('f5') # Refresh the browser with updated data
    except Exception as e:
        print(f"Error during fetching or processing: {e}")

#fetch_and_update_map('companies.csv', include_disasters=True)  # Initial Display of Map
webbrowser.open('file://' + os.path.realpath('updated_all_companies_map.html'))  # Open the map in the browser

# Automatically update the map on a schedule (minutes)
schedule_hours = 11 * 60 * 60  # 12 hours in seconds
Schedule_minutes = 59  * 60  # 59 minutes in seconds
schedule.every(schedule_hours).seconds.do(fetch_and_update_map, include_disasters=True, csv_path='companies.csv')
countdown = schedule_hours + Schedule_minutes  # 11 hours and 59 minutes in seconds

while countdown > 0:
    print(f"Schedule running...Next update in {countdown // 3600} hours and {(countdown % 3600) // 60} minutes.", end='\r')
    time.sleep(60)  # Sleep for 1 minute
    countdown -= 60
while True:
    schedule.run_pending()