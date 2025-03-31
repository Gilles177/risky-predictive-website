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
import geopandas as gpd
from branca.colormap import LinearColormap

# --- Configuration ---
st.set_page_config(page_title="Chicago Crime Predictor", layout="wide")
st.title("Chicago Crime Risk Assessment")

# --- Introduction ---
st.markdown("""
This app predicts potential crime risks in Chicago based on historical data.

**Important:** This model does not account for inherent biases in the data.

**How to Use:**
1. Select a date and time.
2. Choose a ward via map or dropdown.
3. Click 'Predict Crime Risks'.
""")

# --- Data Loading ---
@st.cache_data
def load_data():
    csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")
    try:
        df = pd.read_csv(csv_path)
        gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df['the_geom']), crs="EPSG:4326")
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.001, preserve_topology=True)
        return gdf
    except FileNotFoundError:
        st.error(f"Error: File '{csv_path}' not found.")
        return None
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

ward_gdf = load_data()
if ward_gdf is None:
    st.stop()

# --- Ward Selection ---
st.header("1. Select Ward")

chicago_coords = [41.8781, -87.6298]
m = folium.Map(location=chicago_coords, zoom_start=10)

def create_ward_map(gdf, map_obj):
    def style_func(feature):
        return {"fillColor": "#69b3a2", "color": "#333", "weight": 1, "fillOpacity": 0.5}

    folium.GeoJson(
        gdf,
        name="Wards",
        tooltip=folium.features.GeoJsonTooltip(fields=["Ward"], aliases=["Ward:"], localize=True),
        style_function=style_func,
    ).add_to(map_obj)

create_ward_map(ward_gdf, m)
map_output = st_folium(m, height=450, width=700)

selected_ward = None
if map_output.get('last_clicked'):
    lat, lon = map_output['last_clicked']['lat'], map_output['last_clicked']['lng']
    point = Point(lon, lat)
    for _, row in ward_gdf.iterrows():
        if row['geometry'].contains(point):
            selected_ward = row['Ward']
            break
else:
    wards = sorted(ward_gdf['Ward'].unique())
    selected_ward = st.selectbox("Or choose a ward:", wards)

# --- Time Selection ---
st.header("2. Select Time Parameters")

def get_prediction_time():
    time_options = {
        "Late Night (12AM-6AM)": (0, 6),
        "Early Morning (6AM-9AM)": (6, 9),
        "Late Morning (9AM-12PM)": (9, 12),
        "Early Noon (12PM-3PM)": (12, 15),
        "Late Noon (3PM-6PM)": (15, 18),
        "Early Night (6PM-12AM)": (18, 24)
    }
    label = st.selectbox("Time period:", list(time_options.keys()))
    date = st.date_input("Date:", datetime.today())
    start, end = time_options[label]
    middle_hour = (start + end) / 2
    return (datetime.combine(date, datetime.min.time()) + timedelta(hours=middle_hour)).strftime("%Y-%m-%d %H:%M")

prediction_time = get_prediction_time()

# --- Prediction Function ---
@st.cache_data(ttl=3600)
def fetch_prediction(ward, time):
    api_url = "https://rpp2-589897242504.europe-west1.run.app/predict"
    payload = {"ward": ward, "date_of_occurrence": time, "latitude": 41.8781, "longitude": -87.6298}
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None

# --- Display Results ---
st.header("3. Get Prediction")
if st.button("Predict Crime Risks"):
    if selected_ward:
        with st.spinner("Analyzing data..."):
            prediction = fetch_prediction(selected_ward, prediction_time)
            if prediction:
                # Crime Risks Chart
                st.subheader("Predicted Crime Probabilities")
                crimes = list(prediction["crime_types_probability"].keys())
                probs = [round(p * 100, 1) for p in prediction["crime_types_probability"].values()]
                fig = go.Figure(go.Bar(x=crimes, y=probs, marker_color='crimson', text=probs, texttemplate='%{text}%', textposition='outside'))
                fig.update_layout(yaxis_title="Probability (%)", xaxis_title="Crime Type", height=500)
                st.plotly_chart(fig, use_container_width=True)

                # Ward Demographics
                st.subheader("Ward Demographics")
                ward_data = ward_gdf[ward_gdf['Ward'] == selected_ward].iloc[0]

                # Race Pie Chart
                race_data = {"Race": ["White", "Black", "Asian", "Hispanic"], "Percentage": [ward_data['Race-White_pct'], ward_data['Race-Black_pct'], ward_data['Race-Asian_pct'], ward_data['Ethnicity-Hispanic_pct']]}
                race_fig = px.pie(race_data, values='Percentage', names='Race', title='Racial Composition')
                st.plotly_chart(race_fig, use_container_width=True)

                # Income Bar Chart
                income_data = {"Income Bracket": ["<25k", "25k-50k", "50k-100k", "100k-150k", ">150k"], "Percentage": [ward_data['Income-24999_minus_pct'], ward_data['Income-25000-49999_pct'], ward_data['Income-50000-99999_pct'], ward_data['Income-100000-149999_pct'], ward_data['Income-150000_plus_pct']]}
                income_fig = px.bar(income_data, x='Income Bracket', y='Percentage', title='Income Distribution')
                st.plotly_chart(income_fig, use_container_width=True)
            else:
                st.warning("Prediction unavailable.")
    else:
        st.warning("Select a ward to proceed.")
