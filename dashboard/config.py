"""Central configuration for the REWEAVE · Barnadi Grassland dashboard.

Everything that is a *choice* (names, colours, class definitions, layout sizes)
lives here so the rest of the code stays free of magic values.
The class definitions, colours and NDVI breaks mirror the processing notebook
(`Combined_VegProp_AGB_Dashboard.ipynb`) so the dashboard and the notebook agree.
"""
from __future__ import annotations

import os
from pathlib import Path

# =========================================================================== #
#  EASY SETTINGS  –  the things you are most likely to want to tweak.
#  Edit a value, commit on GitHub, and Streamlit Cloud redeploys by itself.
# =========================================================================== #
HEADER_ORG_PX = 28            # header: size of "REWEAVE COLLECTIVES"  (big)
HEADER_LANDSCAPE_PX = 13      # header: size of "Barnadi Grassland"    (small)
CARBON_UNIT = "tonnes C"      # unit shown for carbon / biomass (avoids a capital "T")
AGB_VMIN, AGB_VMAX = 0.0, 160.0   # AGB colour scale + legend range (Mg/ha); data spans ~19-158

# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
ORG_NAME = "REWEAVE Collectives"
LANDSCAPE = "Barnadi Grassland"
LOCATION = "Udalguri, Assam"
PAGE_TITLE = f"{LANDSCAPE} · {ORG_NAME}"
PANEL_TITLE = "Vegetation Propagation & Above-Ground Biomass"

# --------------------------------------------------------------------------- #
# Data location (mirrors the notebook's OUTPUT_DIR layout)
# Override with the REWEAVE_DATA_DIR environment variable if needed.
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("REWEAVE_DATA_DIR", ROOT / "data" / "Outputs_VegProp_AGB"))

AOI_CANDIDATES = ("Grassland_plot.json", "Grassland_plot.geojson")
LOGO_FILE = "reweave_logo.png"
TABLES_FILE = "VegProp_AGB_Area_Biomass_Tables.xlsx"

SUBDIRS = {
    "ndvi": "1_NDVI",
    "veg": "2_VegetationPropagation",
    "cdb": "3_ChangeDetection_Baseline",
    "cdp": "4_ChangeDetection_MonthToMonth",
    "agb": "5_AGB_10m_AOI",
    "agbn": "5_AGB_native30m_bbox",
}
# glob patterns used to find each monthly raster ({code} = e.g. "Oct_2025")
RASTER_PATTERNS = {
    "veg": "VegPropagation_{code}_*.tif",
    "ndvi": "NDVI_median_{code}_*.tif",
    "agb": "AGB_MgPerHa_{code}_*_AOI.tif",
}

SHEET_A, SHEET_B, SHEET_C, SHEET_D, SHEET_INFO = (
    "A_VegProp_Area", "B_CD_Baseline_to_Month", "C_CD_Prev_to_Current",
    "D_AGB_Harvest", "Plot_Info",
)

# --------------------------------------------------------------------------- #
# Vegetation-propagation classes (notebook CONFIG)
# --------------------------------------------------------------------------- #
CLASS_MAP = {0: "Non-Vegetation", 1: "Sparse Vegetation", 2: "Moderate Vegetation", 3: "Dense Vegetation"}
COLOR_MAP = {"Non-Vegetation": "#d7191c", "Sparse Vegetation": "#fdae61",
             "Moderate Vegetation": "#a6d96a", "Dense Vegetation": "#1a9641"}
CLASS_ORDER = list(CLASS_MAP.values())
NDVI_BREAKS_TEXT = "NDVI breaks: <0.2 | 0.2-0.4 | 0.4-0.6 | ≥0.6"

NDVI_VMIN, NDVI_VMAX = -0.1, 0.8
CMAP_NDVI, CMAP_AGB = "RdYlGn", "YlGn"
LAYERS = {"agb": "AGB (Mg/ha)", "ndvi": "NDVI", "veg": "Vegetation propagation"}

# --------------------------------------------------------------------------- #
# Basemap
# --------------------------------------------------------------------------- #
BASEMAP_NAME = "Esri World Imagery"      # satellite imagery (not ESA WorldCover)
BASEMAP_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
BASEMAP_ATTR = "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics"
AOI_LINE_COLOR = "#5cc8f2"

# --------------------------------------------------------------------------- #
# Dark theme: carbon black + dark grey, with dark-olive accents
# --------------------------------------------------------------------------- #
PALETTE = {
    "bg": "#0a0b09",          # carbon black (page)
    "surface": "#121311",
    "card": "#171916",        # dark grey (cards)
    "border": "#2b2e27",
    "text": "#e9eae3",
    "muted": "#9a9e8f",
    "accent": "#9aab4d",      # olive (lines, highlights, active slider)
    "olive": "#5c6a2a",       # dark olive (selected tab fill)
    "olive_hi": "#6d7d33",
    "beige": "#cfc28a",       # khaki (organisation name)
    "amber": "#f2b45a",
    "sky": "#5cc8f2",
    "grid": "rgba(233,234,227,0.08)",
}

# --------------------------------------------------------------------------- #
# Layout (px).  The map card is deliberately larger than in the notebook
# (notebook: 420 px card / 7:5 split  ->  here: 510 px card / 8:5 split).
# --------------------------------------------------------------------------- #
MAIN_SPLIT = [8, 5]            # map : sankey column ratio
H_MAIN = 500                   # height of the map / sankey cards
H_BOTTOM = 204                 # height of the bottom-row cards
H_CTL = 72                     # height of the dropdown / KPI cards
CARD_PAD = 8
CARD_HEAD = 30                 # card header strip
SLIDER_BLOCK = 84              # time-slider block under the map
MAP_H = H_MAIN - 2 * CARD_PAD - CARD_HEAD - SLIDER_BLOCK - 12
CHART_H_MAIN = H_MAIN - 2 * CARD_PAD - CARD_HEAD - 8
CHART_H_BOTTOM = H_BOTTOM - 2 * CARD_PAD - CARD_HEAD - 6
MAP_FIT_WIDTH = 760            # width assumed when computing the initial zoom
