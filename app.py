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

st.set_page_config(page_title="PredPol 2.0", layout="wide")
st.title("PredPol 2.0: Crime Predictions")

if 'selected_coords' not in st.session_state:
    st.session_state.selected_coords = None
if 'selected_ward' not in st.session_state:
    st.session_state.selected_ward = None

def load_ward_boundaries():
    csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")
    ward_bound = pd.read_csv(csv_path)
    ward_bound['the_geom'] = ward_bound['the_geom'].apply(wkt.loads)
    return gpd.GeoDataFrame(ward_bound, geometry='the_geom', crs="EPSG:4326")

if 'ward_data' not in st.session_state:
    st.session_state.ward_data = load_ward_boundaries()
    st.session_state.ward_bound = pd.read_csv(os.path.join("raw_data", "ward_demographics_boundaries.csv"))

def find_ward(lat, lon):
    point = Point(lon, lat)
    for _, row in st.session_state.ward_data.iterrows():
        if row['the_geom'].contains(point):
            return row['Ward']
    return None

chicago_coords = [41.8781, -87.6298]
m = folium.Map(location=chicago_coords, zoom_start=10)

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

for i, (column, name) in enumerate(layer_name_mapping.items()):
    colormap = LinearColormap(['green', 'yellow', 'red'], vmin=0, vmax=100, caption='Percentage (%)')
    folium.GeoJson(
        st.session_state.ward_data,
        name=name,
        tooltip=folium.features.GeoJsonTooltip(fields=["Ward", column], aliases=["Ward:", f"{name}:"]),
        style_function=lambda x, col=column: {
            "fillColor": colormap(x['properties'].get(col, 0)),
            "color": "blue", "weight": 1.5, "fillOpacity": 0.6
        },
        highlight_function=lambda x, col=column: {
            "fillColor": colormap(x['properties'].get(col, 0)),
            "color": "red", "weight": 2, "fillOpacity": 0.8
        },
        show=(i == 0),
    ).add_to(m)

folium.LayerControl().add_to(m)
with st.container():
    st.header("Chicago Ward Map")
    map_output = st_folium(m, height=500, width=1000)
    if map_output.get('last_clicked'):
        lat, lon = map_output['last_clicked']['lat'], map_output['last_clicked']['lng']
        st.session_state.selected_coords = (lat, lon)
        st.session_state.selected_ward = find_ward(lat, lon)

st.sidebar.header("Input Parameters")
if st.session_state.selected_coords:
    lat, lon = st.session_state.selected_coords
    st.sidebar.write(f"**Selected Location:**\n- Latitude: {lat:.4f}\n- Longitude: {lon:.4f}")
    st.sidebar.write(f"- Ward: {st.session_state.selected_ward}" if st.session_state.selected_ward else "Location not within a ward")
else:
    st.sidebar.info("Click on the map to select a location")

selected_date = st.sidebar.date_input("Select Date", datetime.today())
categories = ["Late Night (00:00 to 06:00)", "Early Morning (06:00 to 09:00)", "Late Morning (09:00 to 12:00)", "Early Noon (12:00 to 15:00)", "Late Noon (15:00 to 18:00)", "Early Night (18:00 to 24:00)"]
selected_category = st.sidebar.selectbox("Select Time Category", categories)
time_ranges = {"Late Night (00:00 to 06:00)": (0, 6), "Early Morning (06:00 to 09:00)": (6, 9), "Late Morning (09:00 to 12:00)": (9, 12), "Early Noon (12:00 to 15:00)": (12, 15), "Late Noon (15:00 to 18:00)": (15, 18), "Early Night (18:00 to 24:00)": (18, 24)}
middle_time = datetime.combine(selected_date, datetime.min.time()) + timedelta(hours=sum(time_ranges[selected_category])/2)
middle_time = middle_time.strftime("%Y-%m-%d %H:%M")

api_url = st.sidebar.text_input("API URL", "https://rpp2-589897242504.europe-west1.run.app/predict")
if st.sidebar.button("Get Prediction"):
    if not all([st.session_state.selected_coords, st.session_state.selected_ward, middle_time]):
        st.sidebar.error("Please select a location and ensure all parameters are set")
    else:
        lat, lon = st.session_state.selected_coords
        ward = st.session_state.selected_ward
        payload = {"ward": ward, "date_of_occurrence": middle_time, "latitude": lat, "longitude": lon}
        try:
            with st.spinner("Fetching prediction..."):
                response = requests.post(api_url, json=payload)
                if response.status_code == 200:
                    st.success("Prediction successful!")
                    data = response.json()
                    st.plotly_chart(go.Figure([go.Bar(x=list(data["crime_types_probability"].keys()),
                                                       y=[v * 100 for v in data["crime_types_probability"].values()],
                                                       name="Probability (%)", marker_color='skyblue')]), use_container_width=True)
                else:
                    st.error(f"API Error: {response.status_code}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
