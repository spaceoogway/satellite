import tempfile
import ee
import geemap.foliumap as geemap
import pandas as pd
import geopandas as gpd
import ast
from shapely.geometry import Polygon, mapping
import folium
import random
import streamlit as st

# 1) Use a wide layout so Streamlit uses the full browser width.
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# 2) Inject custom CSS to remove header/footer, eliminate padding,
#    and enforce 100% height + min-height on the main container.
st.markdown(
    """
    <style>
    /* Hide Streamlit header and footer */
    header[data-testid="stHeader"], footer {
        display: none !important;
    }
    /* Remove extra padding in the main container AND ensure min-height: 100vh */
    .block-container {
        margin: 0 !important;
        padding: 0 !important;
        min-height: 100vh !important; /* Critical to avoid white space at bottom */
    }
    /* Force body and html to occupy full screen */
    html, body {
        height: 100%;
        width: 100%;
        margin: 0;
        padding: 0;
        overflow: hidden; /* Hides any scrollbars if content overflows */
    }
    /* Force the outermost Streamlit container to fill the page */
    [data-testid="stAppViewContainer"] {
        height: 100% !important;
        width: 100% !important;
        margin: 0;
        padding: 0;
    }
    /* Force its direct child to also fill the page */
    [data-testid="stAppViewContainer"] > div {
        height: 100% !important;
        width: 100% !important;
        margin: 0;
        padding: 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Access your secrets from .streamlit/secrets.toml
SERVICE_ACCOUNT = st.secrets["ee"]["SERVICE_ACCOUNT"]
KEY_FILE_JSON = st.secrets["ee"]["KEY_FILE_JSON"]
GOOGLE_CLOUD_PROJECT = st.secrets["ee"]["GOOGLE_CLOUD_PROJECT"]

def initialize_ee():
    # Write the fixed JSON key to a temporary file.
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp:
        temp.write(KEY_FILE_JSON)
        temp.flush()
        key_file_path = temp.name

    credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, key_file_path)
    ee.Initialize(credentials, project=GOOGLE_CLOUD_PROJECT)

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

def main():
    initialize_ee()
    center = [39.9052, 32.8112]
    buffer = 0.02
    aoi = ee.Geometry.Rectangle([
        center[1] - buffer, center[0] - buffer,
        center[1] + buffer, center[0] + buffer
    ])
    start_date = "2023-06-01"
    end_date = "2023-06-28"
    image = get_satellite_image(aoi, start_date, end_date)
    ndvi = compute_ndvi(image)

    # Create base map; we will update NDVI after masking.
    m = create_map(center, ndvi)

    parks_union = add_park_polygons(m, "data/park_polygons.csv")
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
    m.addLayerControl()
    m.to_streamlit(height=1000)

if __name__ == "__main__":
    main()