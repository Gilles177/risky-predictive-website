import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely import wkt
import folium
from streamlit_folium import st_folium
import plotly.express as px
import os

# Initialize all session state variables upfront
if 'selected_coords' not in st.session_state:
    st.session_state.selected_coords = None
if 'selected_ward' not in st.session_state:
    st.session_state.selected_ward = None

# Load data without caching
def load_data():
    try:
        df = pd.read_csv("raw_data/ward_demographics_boundaries.csv")
        df['geometry'] = df['the_geom'].apply(wkt.loads)
        return gpd.GeoDataFrame(df, geometry='geometry')
    except Exception as e:
        st.error(f"Data loading failed: {str(e)}")
        return None

# Simple ward finder
def find_ward(lat, lon, gdf):
    point = Point(lon, lat)
    for _, row in gdf.iterrows():
        if row['geometry'].contains(point):
            return row['Ward']
    return None

# Main App
def main():
    st.title("Crime Prediction App")
    
    # Load data
    gdf = load_data()
    if gdf is None:
        return

    # Create basic map
    m = folium.Map(location=[41.8781, -87.6298], zoom_start=10)
    
    # Add simple style function
    def style_function(feature):
        return {
            'fillColor': '#ffff00',
            'color': '#000000',
            'weight': 1,
            'fillOpacity': 0.7
        }
    
    folium.GeoJson(
        gdf,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=['Ward'])
    ).add_to(m)

    # Display map
    map_data = st_folium(m, width=700, height=500)
    
    # Handle map clicks
    if map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]
        st.session_state.selected_coords = (lat, lon)
        st.session_state.selected_ward = find_ward(lat, lon, gdf)
        st.write(f"Selected Ward: {st.session_state.selected_ward}")

    # Prediction form
    with st.form("prediction_form"):
        date = st.date_input("Date", datetime.today())
        time = st.time_input("Time", datetime.now().time())
        submitted = st.form_submit_button("Predict")
        
        if submitted and st.session_state.selected_ward:
            try:
                response = requests.post(
                    "https://your-api-endpoint.com/predict",
                    json={
                        "ward": st.session_state.selected_ward,
                        "date": date.strftime("%Y-%m-%d"),
                        "time": time.strftime("%H:%M")
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    st.plotly_chart(px.bar(
                        x=list(data["probabilities"].keys()),
                        y=list(data["probabilities"].values()),
                        title="Crime Probability"
                    ))
            except Exception as e:
                st.error(f"Prediction failed: {str(e)}")

if __name__ == "__main__":
    main()
