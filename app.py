import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely import wkt
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from branca.colormap import LinearColormap
import os
import plotly.express as px

# Page Configuration
st.set_page_config(page_title="PredPol 2.0", layout="wide")

# Page Title
st.title("PredPol 2.0: Crime Predictions")

# Initialize Session State
if 'selected_coords' not in st.session_state:
    st.session_state.selected_coords = None
if 'selected_ward' not in st.session_state:
    st.session_state.selected_ward = None

# Introduction
st.markdown("""
Predict top crimes and incidents in Chicago using 2023-2024 crime data.

**Note:** This app does not account for biases in historical data.

### How to Use
1) Pick a Date and Time
2) Select a Ward on the map
3) Click "Get Prediction"
""")

# Data Loading - Simplified to avoid caching issues
def load_ward_boundaries():
    """Load ward boundaries without caching"""
    csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")
    ward_bound = pd.read_csv(csv_path)
    ward_bound['the_geom'] = ward_bound['the_geom'].apply(wkt.loads)
    return gpd.GeoDataFrame(ward_bound, geometry='the_geom', crs="EPSG:4326")

# Load data once and store in session state
if 'ward_data' not in st.session_state:
    st.session_state.ward_data = load_ward_boundaries()
    st.session_state.ward_bound = pd.read_csv(os.path.join("raw_data", "ward_demographics_boundaries.csv"))

# Ward finding function without caching
def find_ward(lat, lon):
    """Find ward for given coordinates"""
    point = Point(lon, lat)
    for _, row in st.session_state.ward_data.iterrows():
        if row['the_geom'].contains(point):
            return row['Ward']
    return None

# Map Configuration
def create_layer(gdf, column_name, layer_name, show_layer=False):
    """Create a folium map layer"""
    colormap = LinearColormap(['green', 'yellow', 'red'],
                             vmin=0, vmax=100,
                             caption='Percentage (%)')

    style = {
        "fillColor": lambda x: colormap(x['properties'][column_name]),
        "color": "blue",
        "weight": 1.5,
        "fillOpacity": 0.6,
    }

    highlight = {
        "fillColor": lambda x: colormap(x['properties'][column_name]),
        "color": "red",
        "weight": 2,
        "fillOpacity": 0.8,
    }

    layer = folium.GeoJson(
        gdf,
        name=layer_name,
        tooltip=folium.features.GeoJsonTooltip(
            fields=["Ward", column_name],
            aliases=["Ward:", f"{layer_name}:"],
            localize=True
        ),
        style_function=lambda x: style,
        highlight_function=lambda x: highlight,
        show=show_layer,
    )
    return layer, colormap

# Create Map
chicago_coords = [41.8781, -87.6298]
m = folium.Map(location=chicago_coords, zoom_start=10)

# Layer Configuration
layer_name_mapping = {
    "Race-White_pct": "White Population (%)",
    "Race-Black_pct": "Black Population (%)",
    "Race-Asian_pct": "Asian Population (%)",
    "Ethnicity-Hispanic_pct": "Hispanic Population (%)",
    "Income-24999_minus_pct": "Income <$25k (%)",
    "Income-25000-49999_pct": "Income $25k-$50k (%)",
    "Income-50000-99999_pct": "Income $50k-$100k (%)",
    "Income-100000-149999_pct": "Income $100k-$150k (%)",
    "Income-150000_plus_pct": "Income >$150k (%)"
}

# Add Layers to Map
for i, (col, name) in enumerate(layer_name_mapping.items()):
    layer, colormap = create_layer(st.session_state.ward_data, col, name, show_layer=(i==0))
    layer.add_to(m)
    if i == 0:
        colormap.add_to(m)

folium.LayerControl().add_to(m)

# Display Map
with st.container():
    st.header("Chicago Ward Map")
    map_output = st_folium(m, height=500, width=1000)

    # Handle Map Clicks
    if map_output.get('last_clicked'):
        lat = map_output['last_clicked']['lat']
        lon = map_output['last_clicked']['lng']
        st.session_state.selected_coords = (lat, lon)
        st.session_state.selected_ward = find_ward(lat, lon)

# Sidebar Configuration
st.sidebar.header("Input Parameters")

# Display Selected Location
if st.session_state.selected_coords:
    lat, lon = st.session_state.selected_coords
    st.sidebar.write(f"**Selected Location:**")
    st.sidebar.write(f"- Latitude: {lat:.4f}")
    st.sidebar.write(f"- Longitude: {lon:.4f}")
    if st.session_state.selected_ward:
        st.sidebar.write(f"- Ward: {st.session_state.selected_ward}")
    else:
        st.sidebar.warning("Location not within a Chicago ward")
else:
    st.sidebar.info("Click on the map to select a location")

# Time Selection
def get_middle_time(category, date):
    """Calculate middle time for a time category"""
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

# Date and Time Selection
selected_date = st.sidebar.date_input("Select Date", datetime.today())
categories = list({
    "Late Night (00:00 to 06:00)": (0, 6),
    "Early Morning (06:00 to 09:00)": (6, 9),
    "Late Morning (09:00 to 12:00)": (9, 12),
    "Early Noon (12:00 to 15:00)": (12, 15),
    "Late Noon (15:00 to 18:00)": (15, 18),
    "Early Night (18:00 to 24:00)": (18, 24)
}.keys())
selected_category = st.sidebar.selectbox("Select Time Category", categories)
middle_time = get_middle_time(selected_category, selected_date)

# API Configuration
api_url = st.sidebar.text_input(
    "API URL", 
    "https://rpp2-589897242504.europe-west1.run.app/predict"
)

# Prediction Function
def show_prediction_results(response_data, ward):
    """Display prediction results and demographics"""
    # Crime Prediction Visualization
    labels = list(response_data["crime_types_probability"].keys())
    probabilities = [v * 100 for v in response_data["crime_types_probability"].values()]
    counts = list(response_data["crime_types_count"].values())

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=probabilities,
        name="Probability (%)",
        text=[f"{p:.1f}%" for p in probabilities],
        marker_color='skyblue'
    ))
    fig.add_trace(go.Bar(
        x=labels, y=counts,
        name="Expected Count",
        text=[f"{c}" for c in counts],
        marker_color='orange'
    ))

    fig.update_layout(
        title="Crime Prediction Results",
        xaxis_title="Crime Types",
        barmode='group',
        template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)

    # Demographic Visualization
    st.subheader(f"Demographics for Ward {ward}")
    ward_data = st.session_state.ward_bound[st.session_state.ward_bound['Ward'] == ward]
    
    # Race Distribution
    race_cols = ["Race-White_pct", "Race-Black_pct", "Race-Asian_pct", "Ethnicity-Hispanic_pct"]
    race_names = ["White", "Black", "Asian", "Hispanic"]
    race_values = ward_data[race_cols].iloc[0].values
    st.plotly_chart(px.pie(values=race_values, names=race_names, title="Race Distribution"))
    
    # Income Distribution
    income_cols = ["Income-24999_minus_pct", "Income-25000-49999_pct", 
                  "Income-50000-99999_pct", "Income-100000-149999_pct", 
                  "Income-150000_plus_pct"]
    income_names = ["<$25k", "$25k-$50k", "$50k-$100k", "$100k-$150k", ">$150k"]
    income_values = ward_data[income_cols].iloc[0].values
    st.plotly_chart(px.bar(x=income_names, y=income_values, title="Income Distribution"))

# Prediction Button
st.sidebar.markdown("---")
if st.sidebar.button("Get Prediction", type="primary"):
    if not all([st.session_state.selected_coords, st.session_state.selected_ward, middle_time]):
        st.sidebar.error("Please select a location and ensure all parameters are set")
    else:
        lat, lon = st.session_state.selected_coords
        ward = st.session_state.selected_ward
        
        payload = {
            "ward": ward,
            "date_of_occurrence": middle_time,
            "latitude": lat,
            "longitude": lon,
        }

        try:
            with st.spinner("Fetching prediction..."):
                response = requests.post(api_url, json=payload)
                
                if response.status_code == 200:
                    st.success("Prediction successful!")
                    show_prediction_results(response.json(), ward)
                else:
                    st.error(f"API Error: {response.status_code}")
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
