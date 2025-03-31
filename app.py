import streamlit as st
import requests
import pandas as pd
import geopandas as gpd
import folium
from datetime import datetime, timedelta
from shapely.geometry import Point
from shapely import wkt
from streamlit_folium import st_folium
from branca.colormap import LinearColormap
import plotly.express as px
import plotly.graph_objects as go
import os

# Streamlit Page Config
st.set_page_config(page_title="PredPol 2.0", layout="wide")
st.title("PredPol 2.0: Crime Predictions")

# Initialize Session State
if 'selected_coords' not in st.session_state:
    st.session_state.selected_coords = None
if 'selected_ward' not in st.session_state:
    st.session_state.selected_ward = None

# Load Ward Data
@st.cache_data
def load_ward_boundaries():
    csv_path = "raw_data/ward_demographics_boundaries.csv"
    ward_bound = pd.read_csv(csv_path)
    ward_bound['the_geom'] = ward_bound['the_geom'].apply(wkt.loads)
    return gpd.GeoDataFrame(ward_bound, geometry='the_geom', crs="EPSG:4326")

if 'ward_data' not in st.session_state:
    st.session_state.ward_data = load_ward_boundaries()
    st.session_state.ward_bound = pd.read_csv("raw_data/ward_demographics_boundaries.csv")

# Find Ward Function
def find_ward(lat, lon):
    point = Point(lon, lat)
    for _, row in st.session_state.ward_data.iterrows():
        if row['the_geom'].contains(point):
            return row['Ward']
    return None

# Style Functions
def style_function(feature):
    value = feature['properties'].get("Race-White_pct", 0)
    colormap = LinearColormap(['green', 'yellow', 'red'], vmin=0, vmax=100)
    return {"fillColor": colormap(value), "color": "blue", "weight": 1.5, "fillOpacity": 0.6}

def highlight_function(feature):
    value = feature['properties'].get("Race-White_pct", 0)
    colormap = LinearColormap(['green', 'yellow', 'red'], vmin=0, vmax=100)
    return {"fillColor": colormap(value), "color": "red", "weight": 2, "fillOpacity": 0.8}

# Generate Map
m = folium.Map(location=[41.8781, -87.6298], zoom_start=10)
folium.GeoJson(
    st.session_state.ward_data,
    name="Demographics",
    tooltip=folium.features.GeoJsonTooltip(fields=["Ward"]),
    style_function=style_function,
    highlight_function=highlight_function
).add_to(m)
folium.LayerControl().add_to(m)

# Display Map
with st.container():
    st.header("Chicago Ward Map")
    map_output = st_folium(m, height=500, width=1000)
    if map_output.get('last_clicked'):
        lat, lon = map_output['last_clicked']['lat'], map_output['last_clicked']['lng']
        st.session_state.selected_coords = (lat, lon)
        st.session_state.selected_ward = find_ward(lat, lon)

# Sidebar Inputs
st.sidebar.header("Input Parameters")
if st.session_state.selected_coords:
    lat, lon = st.session_state.selected_coords
    st.sidebar.write(f"**Selected Location:**\n- Latitude: {lat:.4f}\n- Longitude: {lon:.4f}")
    if st.session_state.selected_ward:
        st.sidebar.write(f"- Ward: {st.session_state.selected_ward}")
    else:
        st.sidebar.warning("Location not within a Chicago ward")
else:
    st.sidebar.info("Click on the map to select a location")

# Date & Time Selection
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

selected_date = st.sidebar.date_input("Select Date", datetime.today())
categories = list({"Late Night (00:00 to 06:00)": (0, 6), "Early Morning (06:00 to 09:00)": (6, 9)}.keys())
selected_category = st.sidebar.selectbox("Select Time Category", categories)
middle_time = get_middle_time(selected_category, selected_date)

# API Input
api_url = st.sidebar.text_input("API URL", "https://rpp2-589897242504.europe-west1.run.app/predict")

# Prediction Function
def show_prediction_results(response_data, ward):
    labels = list(response_data["crime_types_probability"].keys())
    probabilities = [v * 100 for v in response_data["crime_types_probability"].values()]
    counts = list(response_data["crime_types_count"].values())
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=probabilities, name="Probability (%)", marker_color='skyblue'))
    fig.add_trace(go.Bar(x=labels, y=counts, name="Expected Count", marker_color='orange'))
    fig.update_layout(title="Crime Prediction Results", xaxis_title="Crime Types", barmode='group')
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader(f"Demographics for Ward {ward}")
    ward_data = st.session_state.ward_bound[st.session_state.ward_bound['Ward'] == ward]
    race_cols = ["Race-White_pct", "Race-Black_pct", "Race-Asian_pct", "Ethnicity-Hispanic_pct"]
    race_values = ward_data[race_cols].iloc[0].values
    st.plotly_chart(px.pie(values=race_values, names=race_cols, title="Race Distribution"))

# Prediction Button
if st.sidebar.button("Get Prediction", type="primary"):
    if not all([st.session_state.selected_coords, st.session_state.selected_ward, middle_time]):
        st.sidebar.error("Please select a location and ensure all parameters are set")
    else:
        payload = {"ward": st.session_state.selected_ward, "date_of_occurrence": middle_time, "latitude": st.session_state.selected_coords[0], "longitude": st.session_state.selected_coords[1]}
        try:
            response = requests.post(api_url, json=payload)
            if response.status_code == 200:
                show_prediction_results(response.json(), st.session_state.selected_ward)
            else:
                st.error(f"API Error: {response.status_code}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
