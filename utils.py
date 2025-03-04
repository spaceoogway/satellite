import geemap.foliumap as geemap
import pandas as pd
import geopandas as gpd
import ast
from shapely.geometry import Polygon, mapping
import folium
import random
import ee
import streamlit as st
import tempfile

def initialize_ee():
    # Access your secrets from .streamlit/secrets.toml
    service_account = st.secrets["ee"]["SERVICE_ACCOUNT"]
    key_file_json = st.secrets["ee"]["KEY_FILE_JSON"]
    google_cloud_project = st.secrets["ee"]["GOOGLE_CLOUD_PROJECT"]
    # Write the fixed JSON key to a temporary file.
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp:
        temp.write(key_file_json)
        temp.flush()
        key_file_path = temp.name

    credentials = ee.ServiceAccountCredentials(service_account, key_file_path)
    ee.Initialize(credentials, project=google_cloud_project)

def create_aoi(center, buffer):
    return ee.Geometry.Rectangle([
        center[1] - buffer, center[0] - buffer,
        center[1] + buffer, center[0] + buffer
    ])

def get_satellite_image(aoi, start_date, end_date):
    collection = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                  .filterBounds(aoi)
                  .filterDate(start_date, end_date)
                  .sort('CLOUDY_PIXEL_PERCENTAGE'))
    image = collection.first()  # Choose the least cloudy image
    return image

def compute_ndvi(image):
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    return ndvi

def load_csv_polygons(csv_file):
    df = pd.read_csv(csv_file)
    df['geometry'] = df['polygon'].apply(lambda x: Polygon(ast.literal_eval(x)))
    colors = ["green", "blue", "red"]
    df['color'] = df.apply(lambda row: random.choice(colors), axis=1)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
    return gdf

def add_park_polygons(m, csv_file):
    gdf = load_csv_polygons(csv_file)
    geojson_data = gdf.to_json()

    def style_function(feature):
        return {
            'color': feature['properties'].get('color', 'blue'),
            'weight': 3,
            'fillOpacity': 0
        }

    geojson_layer = folium.GeoJson(
        geojson_data,
        name="Urban Parks",
        style_function=style_function,
        tooltip=folium.features.GeoJsonTooltip(fields=['name'], aliases=["Park: "])
    )
    geojson_layer.add_to(m)

    union_geom = gdf.union_all()
    ee_union = ee.Geometry(mapping(union_geom))
    return ee_union

def create_map(aoi_center, ndvi_masked):
    # Create the map; center is [lat, lon], zoom=10
    m = geemap.Map(center=aoi_center, zoom=12)
    # Remove default layers
    m.layers = []
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite',
        max_zoom=25,
        name='Google Satellite'
    ).add_to(m)

    ndvi_vis = {
        "min": 0.0,
        "max": 0.8,
        "palette": [
            "FFFFFF", "CE7E45", "DF923D", "F1B555", "FCD163",
            "99B718", "74A901", "66A000", "529400", "3E8601",
            "207401", "056201", "004C00"
        ]
    }
    m.addLayer(ndvi_masked, ndvi_vis, "NDVI (Inside Parks)")
    return m

def add_ndvi_layer(m, parks_union , ndvi):
    mask = ee.Image.constant(1).clip(parks_union)
    ndvi_masked = ndvi.updateMask(mask)
    # Replace any old NDVI layer with the masked one
    m.layers = [
        layer for layer in m.layers
        if getattr(layer, 'layer_name', None) != "NDVI (Inside Parks)"
    ]
    m.addLayer(
        ndvi_masked,
        {
            "min": 0.0,
            "max": 0.8,
            "palette": [
                "FFFFFF", "CE7E45", "DF923D", "F1B555", "FCD163",
                "99B718", "74A901", "66A000", "529400", "3E8601",
                "207401", "056201", "004C00"
            ]
        },
        "NDVI (Inside Parks)"
    )
    return m