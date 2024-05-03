import pandas as pd
import folium
import schedule
import time
import webbrowser
from gdacs.api import GDACSAPIReader

def load_companies_from_csv(file_path):
    return pd.read_csv(file_path)

def check_disaster_vicinity(company_lat, company_lon, disasters_data):
    for disaster in disasters_data:
        disaster_lat, disaster_lon = disaster['coordinates']
        if abs(disaster_lat - company_lat) < 0.5 and abs(disaster_lon - company_lon) < 0.5: #display if within 0.5 degrees Lon & Lat
            return True
    return False

def create_map_from_companies(companies_df, disasters_data):
    if companies_df.empty:
        print("No company data available.")
        return None
    initial_location = [companies_df.iloc[0]['Latitude'], companies_df.iloc[0]['Longitude']]
    company_map = folium.Map(location=initial_location, zoom_start=4)
    for _, row in companies_df.iterrows():
        in_jeopardy = check_disaster_vicinity(row['Latitude'], row['Longitude'], disasters_data)
        color = 'red' if in_jeopardy else 'blue'
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=f"{row['Company_Name']}{' - In Jeopardy!' if in_jeopardy else ''}",
            icon=folium.Icon(color=color)
        ).add_to(company_map)
    
    company_map.save('updated_all_companies_map.html')
    return company_map

def extract_disaster_info(disasters):
    disaster_info = []
    for feature in disasters['features']:  # Correct access to features
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

def fetch_and_update_map(csv_path):
    try:
        client = GDACSAPIReader()
        disaster_data = client.latest_events()  # Get 10 recent events for testing. Remove limits for production
        disaster_data = vars(disaster_data)
        disaster_info = extract_disaster_info(disaster_data)
        companies_df = load_companies_from_csv(csv_path)

        create_map_from_companies(companies_df, disaster_info)
        print("Map updated with the latest disaster data.")
        webbrowser.open('updated_all_companies_map.html')
    except Exception as e:
        print(f"Error during fetching or processing: {e}")

#schedule.every(1).minutes.do(fetch_and_update_map, csv_path='companies.csv')  # Adjusted to every 10 minutes
fetch_and_update_map('companies.csv')  # Initial run
#while True:
    #schedule.run_pending()
    #time.sleep(1)  # Reduce sleep time to improve responsiveness
