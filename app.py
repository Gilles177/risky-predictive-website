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
if 'scroll_to_graph' not in st.session_state:
    st.session_state.scroll_to_graph = False

# Introduction
st.markdown("""
Predict top crimes and incidents in Chicago using 2023-2024 crime data.

**Note:** This app does not account for biases in historical data.

### How to Use
1) Pick a Date and Time
2) Select a Ward on the map
3) Click "Get Prediction"
""")

# Data Loading Functions
@st.cache_data
def load_and_process_data(csv_path):
    """Load and process ward boundary data"""
    ward_bound = pd.read_csv(csv_path)
    ward_bound['the_geom'] = ward_bound['the_geom'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(ward_bound, geometry='the_geom', crs="EPSG:4326")
    gdf['the_geom'] = gdf['the_geom'].simplify(tolerance=0.001, preserve_topology=True)
    return gdf

@st.cache_data
def find_ward(lat, lon, geodataframe):
    """Find ward for given coordinates"""
    point = Point(lon, lat)
    for _, row in geodataframe.iterrows():
        if row['the_geom'].contains(point):
            return row['Ward']
    return None

# Load Data
csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")
gdf = load_and_process_data(csv_path)
st.session_state.ward_bound = pd.read_csv(csv_path)

# Map Configuration
def create_layer(gdf, column_name, layer_name, show_layer=False):
    """Create a folium map layer with colormap"""
    colormap = LinearColormap(['green', 'yellow', 'red'],
                             vmin=0, vmax=100,
                             caption='Percentage (%)')

    def style_function(feature):
        value = feature['properties'][column_name]
        return {
            "fillColor": colormap(value),
            "color": "blue",
            "weight": 1.5,
            "fillOpacity": 0.6,
        }

    def highlight_function(feature):
        return {
            "fillColor": colormap(feature['properties'][column_name]),
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
        style_function=style_function,
        highlight_function=highlight_function,
        show=show_layer,
    ).add_to(m)

    if show_layer:
        colormap.add_to(m)

# Create Map
chicago_coords = [41.8781, -87.6298]
m = folium.Map(location=chicago_coords, zoom_start=10)

# Layer Configuration
percentage_columns = [
    "Race-White_pct", "Race-Black_pct", "Race-Asian_pct",
    "Ethnicity-Hispanic_pct", "Income-24999_minus_pct",
    "Income-25000-49999_pct", "Income-50000-99999_pct",
    "Income-100000-149999_pct", "Income-150000_plus_pct"
]

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
for i, column in enumerate(percentage_columns):
    friendly_name = layer_name_mapping.get(column, column)
    create_layer(gdf, column, friendly_name, show_layer=(i == 0))

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
        st.session_state.selected_ward = find_ward(lat, lon, gdf)

# Sidebar Configuration
st.sidebar.header("Input Parameters")

# Display Selected Location
if st.session_state.selected_coords:
    selected_lat, selected_lon = st.session_state.selected_coords
    st.sidebar.write(f"**Selected Location:**")
    st.sidebar.write(f"- Latitude: {selected_lat:.4f}")
    st.sidebar.write(f"- Longitude: {selected_lon:.4f}")
    if st.session_state.selected_ward:
        st.sidebar.write(f"- Ward: {st.session_state.selected_ward}")
    else:
        st.sidebar.warning("Selected location is not within a Chicago ward")
else:
    st.sidebar.info("Click on the map to select a location")

# Time Selection
def get_middle_time_for_category(category, selected_date):
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
        start_hour, end_hour = time_ranges[category]
        middle_hour = (start_hour + end_hour) / 2
        middle_time = datetime.combine(selected_date, datetime.min.time()) + timedelta(hours=middle_hour)
        return middle_time.strftime("%Y-%m-%d %H:%M")
    return None

# Date and Time Selection
selected_date = st.sidebar.date_input("Select Date", datetime.today())
categories = [
    "Late Night (00:00 to 06:00)", "Early Morning (06:00 to 09:00)",
    "Late Morning (09:00 to 12:00)", "Early Noon (12:00 to 15:00)",
    "Late Noon (15:00 to 18:00)", "Early Night (18:00 to 24:00)"
]
selected_category = st.sidebar.selectbox("Select Time Category", categories)
middle_time = get_middle_time_for_category(selected_category, selected_date)

# API Configuration
api_url = st.sidebar.text_input(
    "API URL", 
    "https://rpp2-589897242504.europe-west1.run.app/predict"
)

# Prediction Button
st.sidebar.markdown("---")
if st.sidebar.button("Get Prediction", type="primary"):
    if not all([st.session_state.selected_coords, st.session_state.selected_ward, middle_time]):
        st.sidebar.error("Please select a location on the map and ensure all parameters are set")
    else:
        selected_lat, selected_lon = st.session_state.selected_coords
        selected_ward = st.session_state.selected_ward
        
        payload = {
            "ward": selected_ward,
            "date_of_occurrence": middle_time,
            "latitude": selected_lat,
            "longitude": selected_lon,
        }

        try:
            with st.spinner("Fetching prediction..."):
                response = requests.post(api_url, json=payload)
                
                if response.status_code == 200:
                    response_data = response.json()
                    
                    # Crime Prediction Visualization
                    st.success("Prediction successful!")
                    
                    # Extract data for visualization
                    labels = list(response_data["crime_types_probability"].keys())
                    probabilities = [v * 100 for v in response_data["crime_types_probability"].values()]
                    counts = list(response_data["crime_types_count"].values())

                    # Create grouped bar chart
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=labels,
                        y=probabilities,
                        name="Probability (%)",
                        text=[f"{p:.1f}%" for p in probabilities],
                        textposition='outside',
                        marker_color='skyblue'
                    ))
                    fig.add_trace(go.Bar(
                        x=labels,
                        y=counts,
                        name="Expected Count",
                        text=[f"{c}" for c in counts],
                        textposition='outside',
                        marker_color='orange'
                    ))

                    # Update layout
                    max_value = max(probabilities)
                    fig.update_layout(
                        title="Crime Prediction Results",
                        xaxis_title="Crime Types",
                        yaxis_title="Values",
                        xaxis=dict(tickangle=-45),
                        barmode='group',
                        template="plotly_white",
                        legend=dict(
                            orientation="h",
                            yanchor="top",
                            y=1.2,
                            xanchor="center",
                            x=0.5
                        ),
                        margin=dict(t=100, b=100),
                        yaxis=dict(range=[0, max_value * 1.1])
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # Demographic Visualization
                    st.subheader(f"Demographics for Ward {selected_ward}")
                    
                    # Rename columns for display
                    st.session_state.ward_bound.rename(columns=layer_name_mapping, inplace=True)
                    ward_data = st.session_state.ward_bound[st.session_state.ward_bound['Ward'] == selected_ward]

                    # Race Distribution Pie Chart
                    race_cols = ["White Population (%)", "Black Population (%)", 
                               "Asian Population (%)", "Hispanic Population (%)"]
                    race_values = ward_data[race_cols].iloc[0].values
                    race_fig = px.pie(values=race_values, names=race_cols, 
                                    title="Race/Ethnicity Distribution")
                    st.plotly_chart(race_fig, use_container_width=True)

                    # Income Distribution Bar Chart
                    income_cols = ["Income <$25k (%)", "Income $25k-$50k (%)", 
                                 "Income $50k-$100k (%)", "Income $100k-$150k (%)", 
                                 "Income >$150k (%)"]
                    income_values = ward_data[income_cols].iloc[0].values
                    
                    income_fig = go.Figure(go.Bar(
                        x=income_cols,
                        y=income_values,
                        marker_color='lightcoral'
                    ))
                    income_fig.update_layout(
                        title="Income Distribution",
                        xaxis_title="Income Ranges",
                        yaxis_title="Percentage (%)",
                        template="plotly_white"
                    )
                    st.plotly_chart(income_fig, use_container_width=True)

                else:
                    st.error(f"API Error: {response.status_code} - {response.text}")
        
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
