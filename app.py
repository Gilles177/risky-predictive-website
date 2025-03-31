import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely import wkt
import plotly.express as px
import plotly.graph_objects as go
import os

# Initialize session state
if 'selected_ward' not in st.session_state:
    st.session_state.selected_ward = None

# Load data
@st.cache_data
def load_data():
    csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")
    ward_bound = pd.read_csv(csv_path)
    ward_bound['geometry'] = ward_bound['the_geom'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(ward_bound, geometry='geometry', crs="EPSG:4326")
    return gdf, ward_bound

gdf, ward_bound = load_data()

# Create Plotly map
def create_map(gdf):
    gdf['center'] = gdf['geometry'].centroid
    gdf['lat'] = gdf['center'].y
    gdf['lon'] = gdf['center'].x
    
    fig = px.scatter_mapbox(gdf, 
                          lat="lat", 
                          lon="lon",
                          hover_name="Ward",
                          hover_data=["Race-White_pct", "Race-Black_pct"],
                          zoom=10)
    
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return fig

# Display map
st.header("Chicago Ward Map")
map_fig = create_map(gdf)
selected_point = st.plotly_chart(map_fig, use_container_width=True)

# Ward selection
wards = sorted(gdf['Ward'].unique())
selected_ward = st.selectbox("Select Ward", wards)
st.session_state.selected_ward = selected_ward

# Time selection
def get_middle_time(category, date):
    time_ranges = {
        "Late Night (00:00 to 06:00)": (0, 6),
        "Early Morning (06:00 to 09:00)": (6, 9),
        "Late Morning (09:00 to 12:00)": (9, 12),
        "Early Noon (12:00 to 15:00)": (12, 15),
        "Late Noon (15:00 to 18:00)": (15, 18),
        "Early Night (18:00 to 24:00)": (18, 24)
    }
    
    if category in time_ranges:
        start, end = time_ranges[category]
        middle = datetime.combine(date, datetime.min.time()) + timedelta(hours=(start+end)/2)
        return middle.strftime("%Y-%m-%d %H:%M")
    return None

selected_date = st.date_input("Select Date", datetime.today())
categories = list({
    "Late Night (00:00 to 06:00)": (0, 6),
    "Early Morning (06:00 to 09:00)": (6, 9),
    "Late Morning (09:00 to 12:00)": (9, 12),
    "Early Noon (12:00 to 15:00)": (12, 15),
    "Late Noon (15:00 to 18:00)": (15, 18),
    "Early Night (18:00 to 24:00)": (18, 24)
}.keys())
selected_category = st.selectbox("Select Time Category", categories)
middle_time = get_middle_time(selected_category, selected_date)

# Prediction function
def get_prediction(ward, date_time):
    api_url = "https://rpp2-589897242504.europe-west1.run.app/predict"
    payload = {
        "ward": ward,
        "date_of_occurrence": date_time,
        "latitude": 41.8781,  # Approximate Chicago coords
        "longitude": -87.6298
    }
    
    try:
        response = requests.post(api_url, json=payload)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error: {str(e)}")
    return None

# Display results
if st.button("Get Prediction") and st.session_state.selected_ward:
    result = get_prediction(st.session_state.selected_ward, middle_time)
    
    if result:
        # Crime prediction chart
        crimes = list(result["crime_types_probability"].keys())
        probs = [v*100 for v in result["crime_types_probability"].values()]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=crimes,
            y=probs,
            name="Probability (%)"
        ))
        st.plotly_chart(fig)
        
        # Demographic data
        ward_data = ward_bound[ward_bound['Ward'] == st.session_state.selected_ward].iloc[0]
        
        # Race pie chart
        race_fig = px.pie(
            values=[ward_data['Race-White_pct'], 
                   ward_data['Race-Black_pct'],
                   ward_data['Race-Asian_pct']],
            names=['White', 'Black', 'Asian']
        )
        st.plotly_chart(race_fig)
