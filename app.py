import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go

# Initialize session state
if 'selected_ward' not in st.session_state:
    st.session_state.selected_ward = None
if 'ward_data' not in st.session_state:
    st.session_state.ward_data = None

# Page configuration
st.set_page_config(page_title="Crime Predictor", layout="wide")
st.title("Chicago Crime Prediction System")

# Data loading - simplified to avoid geopandas issues
@st.cache_data
def load_ward_data():
    try:
        csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        st.error(f"Data loading failed: {str(e)}")
        return None

# Load data
if st.session_state.ward_data is None:
    st.session_state.ward_data = load_ward_data()

if st.session_state.ward_data is None:
    st.stop()

# Ward selection
st.header("1. Select Location")
wards = sorted(st.session_state.ward_data['Ward'].unique())
selected_ward = st.selectbox("Choose a ward:", wards, key='ward_select')
st.session_state.selected_ward = selected_ward

# Time selection
st.header("2. Select Time Parameters")

def get_time_range():
    time_options = {
        "Late Night (12AM-6AM)": (0, 6),
        "Morning (6AM-12PM)": (6, 12),
        "Afternoon (12PM-6PM)": (12, 18),
        "Evening (6PM-12AM)": (18, 24)
    }
    selected_label = st.selectbox("Time period:", list(time_options.keys()))
    selected_date = st.date_input("Date:", datetime.today())
    
    start, end = time_options[selected_label]
    middle_hour = (start + end) / 2
    prediction_time = datetime.combine(selected_date, datetime.min.time()) + timedelta(hours=middle_hour)
    return prediction_time.strftime("%Y-%m-%d %H:%M")

prediction_time = get_time_range()

# Prediction API call
def get_prediction(ward, time_str):
    api_url = "https://rpp2-589897242504.europe-west1.run.app/predict"
    payload = {
        "ward": ward,
        "date_of_occurrence": time_str,
        "latitude": 41.8781,  # Chicago coordinates
        "longitude": -87.6298
    }
    
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Network error: {str(e)}")
        return None

# Display results
st.header("3. Get Prediction")
if st.button("Predict Crime Risks"):
    if st.session_state.selected_ward:
        with st.spinner("Analyzing data..."):
            result = get_prediction(st.session_state.selected_ward, prediction_time)
            
            if result:
                # Crime prediction visualization
                st.subheader("Crime Risk Assessment")
                crimes = list(result["crime_types_probability"].keys())
                probabilities = [round(p*100, 1) for p in result["crime_types_probability"].values()]
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=crimes,
                    y=probabilities,
                    marker_color='crimson',
                    text=probabilities,
                    texttemplate='%{text}%',
                    textposition='outside'
                ))
                fig.update_layout(
                    title="Predicted Crime Probabilities",
                    yaxis_title="Probability (%)",
                    xaxis_title="Crime Type",
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Demographic information
                st.subheader("Ward Demographics")
                ward_info = st.session_state.ward_data[st.session_state.ward_data['Ward'] == st.session_state.selected_ward].iloc[0]
                
                # Race breakdown
                race_data = {
                    "Race": ["White", "Black", "Asian", "Hispanic"],
                    "Percentage": [
                        ward_info['Race-White_pct'],
                        ward_info['Race-Black_pct'],
                        ward_info['Race-Asian_pct'],
                        ward_info['Ethnicity-Hispanic_pct']
                    ]
                }
                race_fig = px.pie(race_data, values='Percentage', names='Race', 
                                 title='Racial Composition')
                st.plotly_chart(race_fig, use_container_width=True)
                
                # Income breakdown
                income_data = {
                    "Income Bracket": ["<25k", "25k-50k", "50k-100k", "100k-150k", ">150k"],
                    "Percentage": [
                        ward_info['Income-24999_minus_pct'],
                        ward_info['Income-25000-49999_pct'],
                        ward_info['Income-50000-99999_pct'],
                        ward_info['Income-100000-149999_pct'],
                        ward_info['Income-150000_plus_pct']
                    ]
                }
                income_fig = px.bar(income_data, x='Income Bracket', y='Percentage',
                                   title='Income Distribution')
                st.plotly_chart(income_fig, use_container_width=True)
            else:
                st.warning("No prediction data returned")
    else:
        st.warning("Please select a ward first")
