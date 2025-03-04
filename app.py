import streamlit as st
import utils

# Use a wide layout so Streamlit uses the full browser width.
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# Inject custom CSS to remove header/footer, eliminate padding,
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


def main():
    # Initialize ee with credentials in .streamlit/secrets.toml
    utils.initialize_ee()
    # Create aoi
    center = [39.9052, 32.8112]
    buffer = 0.02
    aoi = utils.create_aoi(center, buffer)
    # Choose start date and end date
    start_date = "2023-06-01"
    end_date = "2023-06-28"
    # Get satellite image
    image = utils.get_satellite_image(aoi, start_date, end_date)
    # Compute ndvi of the image
    ndvi = utils.compute_ndvi(image)
    # Create base map
    m = utils.create_map(center, ndvi)
    # Add park polygons to the map and return parks union
    parks_union = utils.add_park_polygons(m, "data/park_polygons.csv")
    # Add ndvi layer to the park polygons
    m = utils.add_ndvi_layer(m, parks_union, ndvi)
    # Add layer control
    m.addLayerControl()
    # Put the map to streamlit
    m.to_streamlit(height=1000)

if __name__ == "__main__":
    main()