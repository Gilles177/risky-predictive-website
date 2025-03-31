import streamlit as st
import requests
from datetime import datetime
import  pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely import wkt
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from folium import LayerControl
from branca.colormap import LinearColormap
import os
import plotly.express as px

# Page Title
st.title("PredPol 2.0: Crime Predictions")

# Function to retrieve the Ward using longitude and latitude
csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")

# Function to retrieve the Ward using longitude and latitude

st.session_state.ward_bound = pd.read_csv(csv_path)

# Simplify and Cache GeoDataFrame
@st.cache_data
def load_and_process_data(csv_path):
    ward_bound = pd.read_csv(csv_path)
    # Convert WKT strings to Shapely geometry objects
    ward_bound['the_geom'] = ward_bound['the_geom'].apply(wkt.loads)
    # Create a GeoDataFrame
    gdf = gpd.GeoDataFrame(ward_bound, geometry='the_geom', crs="EPSG:4326")
    gdf['the_geom'] = gdf['the_geom'].simplify(tolerance=0.001, preserve_topology=True)
    return gdf

# Function to find the ward for a given latitude and longitude
def find_ward(lat, lon, geodataframe):
    point = Point(lon, lat)  # Create a Point (longitude first)
    for _, row in geodataframe.iterrows():
        if row['the_geom'].contains(point):  # Check if the point is inside the polygon
            return row['Ward']
    return None  # Return None if no ward contains the point

# Introduction
st.markdown(
    """

    Predict top crimes and incidents in Chicago using 2023-2024 crime data.

    **Note:** This app does not account for biases in historical data.

    ### How to Use

    1) Pick a Date and Time
    2) Select a Ward on the map. Here, also browse demographics of the Ward.
    3) Click "Get Prediction."

    Let's go! :rocket:
    """
)



# Initialize session state for coordinates
if 'selected_coords' not in st.session_state:
    st.session_state.selected_coords = None

# Initialize session state for scrolling
if "scroll_to_graph" not in st.session_state:
    st.session_state.scroll_to_graph = False

# Function to get position as a tuple
@st.cache_data
def load_ward_data():
    csv_path = os.path.join("raw_data", "ward_demographics_boundaries.csv")
    ward_bound = pd.read_csv(csv_path)
    ward_bound['the_geom'] = ward_bound['the_geom'].apply(wkt.loads)
    return gpd.GeoDataFrame(ward_bound, geometry='the_geom', crs="EPSG:4326")

# Load data
gdf = load_and_process_data(csv_path)


# Define the function to create layers with a legend
def create_layer(gdf, column_name, layer_name, show_layer=False):
    colormap = LinearColormap(['green', 'yellow', 'red'],
                              vmin=0, vmax=100,
                          caption='Percentage (%)')  # Add caption for the legend

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

    # Add the GeoJSON layer to the map with tooltips and the defined style
    layer = folium.GeoJson(
        gdf,
        name=layer_name,
        tooltip=folium.features.GeoJsonTooltip(
            fields=["Ward", column_name],
            aliases=["Ward:", f"{layer_name} :"],
            localize=True
        ),
        style_function=style_function,
        highlight_function=highlight_function,
        show=show_layer,  # Show this layer only if `show_layer` is True
    ).add_to(m)

    # Add colormap (legend) to the map only when the layer is active
    if show_layer:
        colormap.add_to(m)

# Initialize map
chicago_coords = [41.8781, -87.6298]
m = folium.Map(location=chicago_coords, zoom_start=10)

# Define GeoDataFrame and column mappings

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

# Add layers with readable names and a legend
for i, column in enumerate(percentage_columns):
    friendly_name = layer_name_mapping.get(column, column)
    create_layer(gdf, column, friendly_name, show_layer=(i == 0))

# Add LayerControl to switch layers
folium.LayerControl().add_to(m)

# Save the map
m.save("map_with_legend.html")

# Render the map using st_folium
map_output = st_folium(m, height=450, width=700)

# Handle map clicks
if map_output.get('last_clicked'):
    lat = map_output['last_clicked']['lat']
    lon = map_output['last_clicked']['lng']
    st.session_state.selected_coords = (lat, lon)

# Display clicked coordinates and ward details
if st.session_state.get('selected_coords'):
    selected_lat, selected_lon = st.session_state.selected_coords
    selected_ward = find_ward(selected_lat, selected_lon, gdf) # Replace with your `find_ward` function logic if needed
    #st.sidebar.write(f"**Latitude:** {selected_lat}")
    #st.sidebar.write(f"**Longitude:** {selected_lon}")
    #st.sidebar.write(f"**Ward:** {selected_ward if selected_ward else 'Not Found'}")
else:
    st.sidebar.write("Click on the map to select a location.")



# Function to return middle time for a range based on category
def get_middle_time_for_category(category, selected_date):
    time_ranges = {
        "Late Night (00:00 to 06:00)": (0, 6),     # Midnight (00:00) to 06:00
        "Early Morning (06:00 to 09:00)": (6, 9),    # 06:00 to 09:00
        "Late Morning (09:00 to 12:00)": (9, 12),    # 09:00 to 12:00
        "Early Noon (12:00 to 15:00)": (12, 15),     # 12:00 to 15:00
        "Late Noon (15:00 to 18:00)": (15, 18),      # 15:00 to 18:00
        "Early Night (18:00 to 24:00)": (18, 24)   # 18:00 to Midnight (24:00)
    }

    # Get the time range for the selected category
    if category in time_ranges:
        start_hour, end_hour = time_ranges[category]
        middle_hour = (start_hour + end_hour) / 2

        # Convert to a datetime object with selected date
        middle_time = datetime.combine(selected_date, datetime.min.time()) + timedelta(hours=middle_hour)
        return middle_time.strftime("%Y-%m-%d %H:%M")  # Format as Date and Time string (24-hour format)

# Function to find the ward for given coordinates
@st.cache_data
def find_ward(lat, lon, geodataframe):
    point = Point(lon, lat)
    for _, row in geodataframe.iterrows():
        if row['the_geom'].contains(point):
            return row['Ward']
    return None

# Sidebar Inputs
st.sidebar.header("Configure Input Parameters")
selected_date = st.sidebar.date_input("Select a Date", datetime.today())

# Sidebar: Dropdown for categories
categories = ["Late Night (00:00 to 06:00)", "Early Morning (06:00 to 09:00)", \
        "Late Morning (09:00 to 12:00)", "Early Noon (12:00 to 15:00)", \
            "Late Noon (15:00 to 18:00)", "Early Night (18:00 to 24:00)"]
selected_category = st.sidebar.selectbox("Select a Time Category", categories)
api_url = st.sidebar.text_input("API URL", "https://rpp-589897242504.europe-west1.run.app/predict")

# Get and display the middle time
if selected_category:
    middle_time = get_middle_time_for_category(selected_category, selected_date)
    if middle_time:
        pass
        #st.sidebar.write(f"### Selected Category: **{selected_category}**")
        #st.write(f"Time: **{middle_time}**")
    else:
        st.sidebar.error("Invalid Category Selected!")


# API URL
api_url = "https://rpp2-589897242504.europe-west1.run.app/predict"

st.sidebar.markdown(
    """
    ---
    ### Make a Prediction
    Once all parameters are set, click the 'Get Prediction' button below to retrieve an offense prediction.
    """
)

# Call API and Get Prediction
if st.sidebar.button("Get Prediction"):
    if api_url and selected_ward and middle_time and selected_lat and selected_lon:
        # Prepare API request payload
        payload = {
            "ward": selected_ward,
            "date_of_occurrence": middle_time,
            "latitude": selected_lat,
            "longitude": selected_lon,
        }

        # Show payload in sidebar for user clarity
        st.sidebar.write(f"Selected Ward is : {selected_ward}")
        st.sidebar.write(f"Selected Date is : {selected_date}")
        st.sidebar.write(f"Selected Time of Day is : {selected_category}")

        try:
            # Make API request
            response = requests.post(api_url, json=payload)
            response_data = response.json()

            # Check if response status is 200 (success)
            if response.status_code == 200:
                # Extract labels, probabilities, and counts from response
                labels = list(response_data["crime_types_probability"].keys())
                probabilities = [v * 100 for v in response_data["crime_types_probability"].values()]  # Convert to percentage
                counts = list(response_data["crime_types_count"].values())

                # Create a grouped bar chart for visualizing probabilities and counts
                fig = go.Figure()

                # Add probabilities bar
                fig.add_trace(go.Bar(
                    x=labels,
                    y=probabilities,
                    name="Likelihood of Offence Occurring (%)",
                    text=[f"{p:.1f}%" for p in probabilities],  # Show percentage text
                    textposition='outside',
                    marker_color='skyblue'
                ))

                # Add counts bar
                fig.add_trace(go.Bar(
                    x=labels,
                    y=counts,
                    name="Probable No. of Occurrences",
                    text=[f"{c}" for c in counts],  # Show count text
                    textposition='outside',
                    marker_color='orange'
                ))
                # Calculate the maximum value across all data series
                max_value = max(probabilities)

                # Customize layout for a more informative and clean display
                fig.update_layout(
                    title="Crime Types: Likelihood and Counts",
                    xaxis_title="Crime Types",
                    yaxis_title="Values",
                    xaxis=dict(tickangle=-45),  # Rotate x-axis labels
                    barmode='group',  # Group bars side by side
                    template="plotly_white",  # Clean background style
                    legend=dict(
                        title="Metrics",
                        orientation="h",  # Set legend orientation to horizontal
                        yanchor="top",  # Align the legend to the bottom of the chart
                        y=1.2,  # Position the legend below the chart (adjust as needed)
                        xanchor="center",  # Center the legend horizontally
                        x=0.5
                    ),
                    margin=dict(t=100, b=100),  # Add margin for better readability
                    yaxis=dict(
                        title="Values",  # Y-axis title
                        range=[0, max_value * 1.1],  # Dynamically set to 10% more than the max value
                        automargin=True  # Automatically adjust for data labels
                    )
                )

                # Display the chart
                st.plotly_chart(fig)

                # Renaming the columns
                st.session_state.ward_bound.rename(columns=layer_name_mapping, inplace=True)

                # Step 2: Filter data based on the selected ward
                selected_ward_data = st.session_state.ward_bound[st.session_state.ward_bound['Ward'] == selected_ward]

                # Now we can extract the relevant demographic data for the selected ward
                race_data = selected_ward_data[[
                    "White Population (%)", "Black Population (%)", "Asian Population (%)", "Hispanic Population (%)"
                ]]
                income_data = selected_ward_data[[
                    "Income <$25k (%)", "Income $25k-$50k (%)", "Income $50k-$100k (%)", "Income $100k-$150k (%)", "Income >$150k (%)"
                ]]

                # Demographic Breakdown for the Selected Ward
                st.subheader(f"Demographic Breakdown for Ward: {selected_ward}")

                # 1. Pie Chart for Race Distribution
                race_values = race_data.iloc[0].values  # Get the first row values for the selected ward
                race_labels = race_data.columns

                race_fig = px.pie(values=race_values, names=race_labels, title="Race Distribution")
                st.plotly_chart(race_fig)

                # # 2. Pie Chart for Ethnicity Distribution
                # ethnicity_values = [selected_ward_data["Hispanic Population (%)"].iloc[0],
                #                     100 - selected_ward_data["Hispanic Population (%)"].iloc[0]]
                # ethnicity_labels = ["Hispanic", "Non-Hispanic"]

                # ethnicity_fig = px.pie(values=ethnicity_values, names=ethnicity_labels, title="Ethnicity Distribution")
                # st.plotly_chart(ethnicity_fig)

                # 3. Bar Chart for Income Distribution
                income_values = income_data.iloc[0].values  # Get the first row values for the selected ward
                income_labels = income_data.columns

                income_fig = go.Figure(go.Bar(
                    x=income_labels,
                    y=income_values,
                    marker_color='lightcoral'
                ))
                income_fig.update_layout(
                    title="Income Distribution",
                    xaxis_title="Income Ranges",
                    yaxis_title="Percentage (%)",
                    template="plotly_white",
                )
                st.plotly_chart(income_fig)


            else:
                st.sidebar.error("Failed to retrieve a valid prediction. Please check your inputs or API.")

        except Exception as e:
            st.sidebar.error(f"An error occurred: {e}")
    else:
        st.sidebar.warning("Please ensure all parameters are filled out correctly.")
