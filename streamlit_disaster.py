import streamlit as st
import pandas as pd
from gdacs.api import GDACSAPIReader
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta

ALERT_LEVELS = {
    'RED': 'Critical',
    'ORANGE': 'High',
    'GREEN': 'Medium',
    'YELLOW': 'Low',
    None: 'Unknown'
}

ALERT_COLORS = {
    'Critical': 'darkred',
    'High': 'red',
    'Medium': 'orange',
    'Low': 'green',
    'Unknown': 'lightgray',
    'Inactive': 'gray'
}

def normalize_alert_level(raw_level):
    """Convert raw API alert level to normalized value."""
    if not raw_level:
        return 'Unknown'
    return ALERT_LEVELS.get(raw_level.upper(), 'Unknown')

def extract_disaster_info(disasters):
    """Extract relevant information from disaster data."""
    disaster_info = []
    try:
        for feature in disasters['features']:
            try:
                properties = feature.get('properties', {})
                geometry = feature.get('geometry', {})
                coords = geometry.get('coordinates', [])
                
                # Get the date information and current status
                is_current = properties.get('iscurrent', 'false').lower() == 'true'
                raw_alert = properties.get('alertlevel')
                normalized_alert = normalize_alert_level(raw_alert)
                
                # Handle coordinates
                if isinstance(coords, (list, tuple)):
                    try:
                        if len(coords) >= 2:
                            coordinates = [float(coords[0]), float(coords[1])]
                        else:
                            continue
                    except (ValueError, TypeError):
                        continue
                else:
                    continue
                
                disaster_info.append({
                    'name': properties.get('name', 'No Name Available'),
                    'disaster_type': properties.get('eventtype', 'Unknown'),
                    'coordinates': coordinates,
                    'alert_level': normalized_alert,
                    'is_current': is_current
                })
            except Exception as e:
                continue
        
        return disaster_info
    except Exception as e:
        st.error(f"Error in extract_disaster_info: {str(e)}")
        return []

def calculate_bounds(disasters_data):
    """Calculate the bounds that encompass all disasters."""
    try:
        if not disasters_data:
            return None
        
        # Filter out any invalid coordinates
        valid_disasters = [d for d in disasters_data if isinstance(d.get('coordinates'), (list, tuple)) 
                         and len(d['coordinates']) >= 2 
                         and all(isinstance(x, (int, float)) for x in d['coordinates'][:2])]
        
        if not valid_disasters:
            return None
            
        lats = [d['coordinates'][1] for d in valid_disasters]
        lons = [d['coordinates'][0] for d in valid_disasters]
        return [[min(lats), min(lons)], [max(lats), max(lons)]]
    except Exception as e:
        st.error(f"Error calculating bounds: {str(e)}")
        return None

def get_marker_color(alert_level, is_current):
    """Determine marker color based on normalized alert level and current status."""
    if not is_current:
        return ALERT_COLORS['Inactive']
    return ALERT_COLORS.get(alert_level, ALERT_COLORS['Unknown'])

def create_map(disasters_data, selected_disaster=None, fit_bounds=None):
    """Create map with disaster markers."""
    try:
        # Verify data before creating map
        if not disasters_data:
            st.warning("No valid disaster data to display")
            return
            
        # Set center coordinates and zoom level
        if selected_disaster and isinstance(selected_disaster.get('coordinates'), (list, tuple)):
            center_coords = selected_disaster['coordinates']
            center_lat, center_lon = float(center_coords[1]), float(center_coords[0])
            zoom_level = 8  # Closer zoom for selected disaster
        else:
            center_lat, center_lon = 0, 0
            zoom_level = 2  # World view for all disasters
            
        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level)
        
        # Add markers with color legend
        marker_counts = {'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0, 'Inactive': 0}
        
        for disaster in disasters_data:
            try:
                coords = disaster['coordinates']
                if not isinstance(coords, (list, tuple)) or len(coords) < 2:
                    continue
                    
                lat, lon = float(coords[1]), float(coords[0])
                # Set color based on alert level and current status
                alert_status = 'Inactive' if not disaster['is_current'] else disaster['alert_level']
                marker_color = ALERT_COLORS.get(alert_status, ALERT_COLORS['Unknown'])
                
                folium.Marker(
                    [lat, lon],
                    popup=f"{disaster['name']} ({disaster['disaster_type']})<br>Alert Level: {alert_status}",
                    icon=folium.Icon(color=marker_color, icon='info-sign')
                ).add_to(m)
                
                marker_counts[alert_status] = marker_counts.get(alert_status, 0) + 1
                
            except Exception as e:
                st.warning(f"Error adding marker: {str(e)}")
                continue
        
        # Add legend text above the map
        legend_text = " | ".join([
            f"{level}: {count} ({ALERT_COLORS[level]} marker{'s' if count != 1 else ''})"
            for level, count in marker_counts.items()
            if count > 0
        ])
        st.markdown(f"**Legend:** {legend_text}")
        
        # Handle bounds and zoom
        if fit_bounds:
            m.fit_bounds(fit_bounds)
        elif selected_disaster:  # If a single disaster is selected, ensure proper zoom
            m.location = [center_lat, center_lon]
            m.zoom_start = zoom_level
        
        st_folium(m, width='100%', height=950, returned_objects=[], use_container_width=True)
        
    except Exception as e:
        st.error(f"Error creating map: {str(e)}")

def fetch_disaster_data(days_back=7, limit=None, min_alert_level=None):
    """Fetch disaster data with configurable parameters"""
    try:
        client = GDACSAPIReader()
        disasters = client.latest_events()
        
        # Handle Pydantic GeoJSON object
        if hasattr(disasters, 'model_dump'):
            disasters = disasters.model_dump()
        
        # Convert to standard format if needed
        if not isinstance(disasters, dict):
            return {'features': []}
        
        features = disasters.get('features', [])
        
        # Filter by date if days_back is specified
        if days_back:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            filtered_features = []
            
            for feature in features:
                try:
                    props = feature.get('properties', {})
                    date_str = props.get('fromdate', '').split('T')[0]
                    event_date = datetime.strptime(date_str, '%Y-%m-%d')
                    if event_date >= cutoff_date:
                        filtered_features.append(feature)
                except (KeyError, ValueError, TypeError) as e:
                    continue
            
            features = filtered_features
        
        return {'features': features}
        
    except Exception as e:
        st.error(f"Error fetching disaster data: {str(e)}")
        return {'features': []}

def get_filtered_disasters(days_back=7, alert_level=None, disaster_type=None):
    disasters = fetch_disaster_data(days_back=days_back, limit=None)
    
    if not disasters or 'features' not in disasters:
        st.warning("No disaster data available")
        return {'features': []}
    
    filtered_disasters = []
    for disaster in disasters['features']:
        if isinstance(disaster, dict) and 'properties' in disaster:
            properties = disaster['properties']
            
            # Normalize the alert level from the API before comparison
            current_alert = normalize_alert_level(properties.get('alertlevel'))
            
            # Check if we should filter by alert level
            if alert_level and alert_level != "All":
                if current_alert != alert_level:
                    continue
            
            # Check if we should filter by disaster type
            if disaster_type:
                current_type = properties.get('eventtype', '').lower()
                if current_type != disaster_type.lower():
                    continue
            
            filtered_disasters.append(disaster)
    
    # Show summary statistics
    total = len(disasters['features'])
    filtered = len(filtered_disasters)
    if alert_level or disaster_type:
        st.info(f"Showing {filtered} of {total} disasters matching your filters")
    else:
        st.info(f"Showing all {total} disasters")
    
    return {'features': filtered_disasters}

def main():
    st.set_page_config(layout="wide")
    
    if 'show_all' not in st.session_state:
        st.session_state.show_all = True
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Add sidebar filters
    st.sidebar.header("Filter Disasters")
    days_back = st.sidebar.slider("Days to look back", 1, 30, 7)
    
    # Update the alert level options to include "All"
    alert_level = st.sidebar.selectbox(
        "Alert Level",
        options=["All", "Critical", "High", "Medium", "Low"],
        format_func=lambda x: x
    )
    
    # Pass None instead of "All" to the filter function
    alert_level_filter = None if alert_level == "All" else alert_level
    
    disaster_type = st.sidebar.selectbox(
        "Disaster Type",
        options=[None, "EQ", "TC", "FL", "VO"],
        format_func=lambda x: "All" if x is None else x
    )
    
    try:
        # Get filtered disaster data with corrected alert level
        disasters = get_filtered_disasters(
            days_back=days_back,
            alert_level=alert_level_filter,
            disaster_type=disaster_type
        )
        disaster_info = extract_disaster_info(disasters)
        
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