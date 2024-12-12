import streamlit as st
import pandas as pd
from gdacs.api import GDACSAPIReader
import folium
from streamlit_folium import st_folium
from datetime import datetime

def extract_disaster_info(disasters):
    # Extract relevant information from disaster data.
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

def calculate_bounds(disasters_data):
    """Calculate the bounds that encompass all disasters."""
    if not disasters_data:
        return None
    
    lats = [d["coordinates"][1] for d in disasters_data]
    lons = [d["coordinates"][0] for d in disasters_data]
    return [[min(lats), min(lons)], [max(lats), max(lons)]]

def create_map(disasters_data, selected_disaster=None, fit_bounds=None):
    # Create base map centered on first disaster or default location
    center_lat = selected_disaster["coordinates"][1] if selected_disaster else 0
    center_lon = selected_disaster["coordinates"][0] if selected_disaster else 0
    zoom_level = 5 if selected_disaster else 2
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)
    
    # Add markers for all disasters
    for disaster in disasters_data:
        lat = disaster["coordinates"][1]
        lon = disaster["coordinates"][0]
        name = disaster["name"]
        d_type = disaster["disaster_type"]
        
        folium.Marker(
            [lat, lon],
            popup=f"{name} ({d_type})",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
    
    # Fit bounds if provided
    if fit_bounds:
        m.fit_bounds(fit_bounds)
    
    # Modified map display settings
    st_folium(
        m,
        width='100%',
        height=625,
        returned_objects=[],
        use_container_width=True
    )

def main():
    st.set_page_config(layout="wide")
    
    if 'show_all' not in st.session_state:
        st.session_state.show_all = True
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Get disaster data first
        client = GDACSAPIReader()
        disaster_data = client.latest_events()
        disaster_data = vars(disaster_data)
        disaster_info = extract_disaster_info(disaster_data)
        
        # Create two columns for title and button
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"<h2 style='margin-bottom:0px'>Worldwide Disaster Mapping ({len(disaster_info)} Events)</h2>", unsafe_allow_html=True)
        with col2:
            if st.button("Refresh Data"):
                st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.rerun()
            st.markdown(f"<p style='font-size: 10px;'>Last refreshed: {st.session_state.last_refresh}</p>", unsafe_allow_html=True)

        # Create sidebar with reduced width
        with st.sidebar.container():
            st.sidebar.header("Disaster List")
            # Add "All Disasters" option to the start of the list
            options = ["All Disasters"] + [f"{d['name']} ({d['disaster_type']})" for d in disaster_info]
            selected_name = st.sidebar.radio(
                "Select a disaster to zoom:",
                options=options,
                key="disaster_selector"
            )

        # Find selected disaster and manage state
        selected_disaster = None
        if selected_name == "All Disasters":
            st.session_state.show_all = True
        else:
            st.session_state.show_all = False
            if selected_name:
                selected_disaster = next(
                    (d for d in disaster_info if f"{d['name']} ({d['disaster_type']})" == selected_name),
                    None
                )

        bounds = calculate_bounds(disaster_info)
        
        # Create map using state to determine zoom
        create_map(
            disaster_info,
            selected_disaster,
            fit_bounds=bounds if st.session_state.show_all else None
        )

    except Exception as e:
        st.error(f"Error during fetching or processing: {e}")

if __name__ == "__main__":
    main()