"""REWEAVE · Barnadi Grassland (Udalguri, Assam) – monitoring dashboard.

Three panels: Geospatial (live, from the pre-processed outputs), Community and Finance (empty for now).
Run locally:   streamlit run app.py
"""
from functools import lru_cache

import streamlit as st

from dashboard import config as C
from dashboard import geospatial
from dashboard import theme as T
from dashboard.data import load_geodata


@lru_cache(maxsize=1)
def _logo():
    """(emblem image for the favicon, emblem as data-URI for the header) – or (None, None)."""
    path = C.DATA_DIR / C.LOGO_FILE
    emblem = T.emblem_image(path if path.exists() else None)
    return (emblem, T.image_to_data_uri(emblem)) if emblem is not None else (None, None)


_emblem, _logo_uri = _logo()
st.set_page_config(page_title=C.PAGE_TITLE, page_icon=_emblem or "🌿", layout="wide",
                   initial_sidebar_state="collapsed")


@st.cache_resource(show_spinner="Loading Barnadi grassland data…")
def get_geodata():
    return load_geodata(C.DATA_DIR)


st.html(T.css())

try:
    geo = get_geodata()
except Exception as exc:                                    # clear message instead of a stack trace
    st.error(f"Could not load the dashboard data from `{C.DATA_DIR}`.\n\n**{type(exc).__name__}:** {exc}")
    st.stop()

st.html(T.header_html(_logo_uri))

tab_geo, tab_com, tab_fin = st.tabs([":material/public: Geospatial", ":material/groups: Community",
                                     ":material/payments: Finance"])
with tab_geo:
    geospatial.render(geo)
with tab_com:
    st.html(T.empty_html("Community", "No data yet — this panel will fill once community data is connected."))
with tab_fin:
    st.html(T.empty_html("Finance", "No data yet — this panel will fill once financial data is connected."))
