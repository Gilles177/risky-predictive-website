import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point
from shapely import wkt
import geopandas as gpd

# Page configuration
st.set_page_config(page_title="Crime Predictor", layout="wide")
st.title("PredPol 2.0: Crime Predictions")

# Introduction
st.markdown("""
Predict top crimes and incidents in Chicago using 2023-2024 crime data.

**Note:** This app does not account for biases in historical data.

### How to Use
1) Pick a Date and Time
2) Select a Ward from the map or dropdown.
3) Click "Get Prediction"
""")

# Data loading
@st.cache_data
def load_ward_data(csv_path):
    try:
        ward_bound = pd.read_csv(csv_path)
        ward_bound['the_geom'] = ward_bound['the_geom'].apply(wkt.loads)
        gdf = gpd.GeoDataFrame(ward_bound, geometry='the_geom', crs="EPSG:4326")
        gdf['the_geom'] = gdf['the_geom'].simplify(tolerance=0.001, preserve_topology=True)
        return gdf
    except FileNotFoundError:
        st.error(f"Error: File not found at {csv_path}")
        return None
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")
ward_gdf = load_ward_data(csv_path)

if ward_gdf is None:
    st.stop()

# Map and Dropdown Selection
st.header("1. Select Ward")
chicago_coords = [41.8781, -87.6298]
m = folium.Map(location=chicago_coords, zoom_start=10)

def create_ward_layer(gdf, m):
    folium.GeoJson(gdf, name="Wards", tooltip=folium.features.GeoJsonTooltip(fields=["Ward"], aliases=["Ward:"], localize=True)).add_to(m)

create_ward_layer(ward_gdf, m)
map_output = st_folium(m, height=450, width=700)

selected_ward = None

if map_output.get('last_clicked'):
    lat = map_output['last_clicked']['lat']
    lon = map_output['last_clicked']['lng']
    point = Point(lon, lat)
    for _, row in ward_gdf.iterrows():
        if row['the_geom'].contains(point):
            selected_ward = row['Ward']
            break
else:
    wards = sorted(ward_gdf['Ward'].unique())
    selected_ward = st.selectbox("Or choose a ward:", wards)

# Time selection
st.header("2. Select Time Parameters")

def get_time_range():
    time_options = {
        "Late Night (12AM-6AM)": (0, 6),
        "Early Morning (6AM-9AM)": (6, 9),
        "Late Morning (9AM-12PM)": (9, 12),
        "Early Noon (12PM-3PM)": (12, 15),
        "Late Noon (3PM-6PM)": (15, 18),
        "Early Night (6PM-12AM)": (18, 24)
    }
    selected_label = st.selectbox("Time period:", list(time_options.keys()))
    selected_date = st.date_input("Date:", datetime.today())
    start, end = time_options[selected_label]
    middle_hour = (start + end) / 2
    prediction_time = datetime.combine(selected_date, datetime.min.time()) + timedelta(hours=middle_hour)
    return prediction_time.strftime("%Y-%m-%d %H:%M")

prediction_time = get_time_range()

# Prediction function
@st.cache_data(ttl=3600)  # Cache API responses for 1 hour
def get_prediction(ward, time_str):
    api_url = "https://rpp2-589897242504.europe-west1.run.app/predict"
    payload = {
        "ward": ward,
        "date_of_occurrence": time_str,
        "latitude": 41.8781,
        "longitude": -87.6298
    }
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None

# Display results
st.header("3. Get Prediction")
if st.button("Predict Crime Risks"):
    if selected_ward:
        with st.spinner("Analyzing data..."):
            result = get_prediction(selected_ward, prediction_time)
            if result:
                st.subheader("Crime Risk Assessment")
                crimes = list(result["crime_types_probability"].keys())
                probabilities = [round(p * 100, 1) for p in result["crime_types_probability"].values()]
                fig = go.Figure(go.Bar(x=crimes, y=probabilities, marker_color='crimson', text=probabilities, texttemplate='%{text}%', textposition='outside'))
                fig.update_layout(title="Predicted Crime Probabilities", yaxis_title="Probability (%)", xaxis_title="Crime Type", height=500)
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Ward Demographics")
                ward_info = ward_gdf[ward_gdf['Ward'] == selected_ward].iloc[0]
                race_data = {"Race": ["White", "Black", "Asian", "Hispanic"], "Percentage": [ward_info['Race-White_pct'], ward_info['Race-Black_pct'], ward_info['Race-Asian_pct'], ward_info['Ethnicity-Hispanic_pct']]}
                race_fig = px.pie(race_data, values='Percentage', names='Race', title='Racial Composition')
                st.plotly_chart(race_fig, use_container_width=True)

                income_data = {"Income Bracket": ["<25k", "25k-50k", "50k-100k", "100k-150k", ">150k"], "Percentage": [ward_info['Income-24999_minus_pct'], ward_info['Income-25000-49999_pct'], ward_info['Income-50000-99999_pct'], ward_info['Income-100000-149999_pct'], ward_info['Income-150000_plus_pct']]}
                income_fig = px.bar(income_data, x='Income Bracket', y='Percentage', title='Income Distribution')
                st.plotly_chart(income_fig, use_container_width=True)
            else:
                st.warning("No prediction data returned.")
    else:
        st.warning("Please select a ward first.")
