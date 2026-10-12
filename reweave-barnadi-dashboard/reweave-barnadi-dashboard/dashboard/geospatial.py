"""Geospatial panel – a Streamlit port of the notebook's Dash dashboard (last two cells).

Same structure and logic as the notebook:
  * controls + KPIs row  ->  raster-layer dropdown | harvested biomass | total AGB | Sankey dropdown
  * main row             ->  map (+ time slider)   | Sankey (or baseline bar chart in the first month)
  * bottom row           ->  vegetation area stack | harvest-area & plot-area KPIs | biomass trend | legend

Difference requested by the user: the two dropdowns are *swapped* so each sits directly above the
panel it controls (raster layer above the map, Sankey transition above the Sankey), and the map card
is larger than in the notebook.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from . import config as C
from . import theme as T
from .data import GeoData

P = C.PALETTE
SANKEY_MODES = {"baseline": "baseline", "previous": "previous"}
GRAPH_CFG = {"displayModeBar": False}
MAP_CFG = {"displayModeBar": False, "scrollZoom": True}


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #
def _initial_zoom(geo: GeoData) -> float:
    """Zoom that fits the plot polygon with ~20 % breathing room (same formula as the notebook)."""
    lon0, lat0, lon1, lat1 = geo.bbox_wgs
    cos = max(float(np.cos(np.radians(geo.center[1]))), 0.2)
    sx, sy = max(lon1 - lon0, 1e-6), max((lat1 - lat0) / cos, 1e-6)
    z = min(np.log2(C.MAP_FIT_WIDTH * 360 / (512 * sx * 1.25)), np.log2(C.MAP_H * 360 / (512 * sy * 1.25)))
    return float(np.clip(z, 3, 19))


def map_figure(geo: GeoData, layer: str, idx: int) -> go.Figure:
    uri, coords = geo.overlays[(layer, idx)]
    lon, lat = geo.center
    layers = [
        {"below": "traces", "sourcetype": "raster", "type": "raster", "source": [C.BASEMAP_URL],
         "sourceattribution": C.BASEMAP_ATTR},
        {"sourcetype": "image", "type": "raster", "source": uri, "coordinates": coords, "opacity": 0.86},
        {"sourcetype": "geojson", "type": "line", "source": geo.aoi_geojson, "color": C.AOI_LINE_COLOR,
         "line": {"width": 2.5}},
    ]
    fig = go.Figure(go.Scattermap(lat=[lat], lon=[lon], mode="markers", marker={"size": 1, "opacity": 0},
                                  hoverinfo="none", showlegend=False))
    fig.update_layout(map=dict(style="white-bg", zoom=_initial_zoom(geo), center=dict(lat=lat, lon=lon), layers=layers),
                      uirevision="keep")
    return T.style_fig(fig, C.MAP_H, margin=dict(l=0, r=0, t=0, b=0))


def baseline_bars(geo: GeoData) -> go.Figure:
    col = f"{geo.months[0].short}_area"
    t = geo.tbl_a
    fig = go.Figure(go.Bar(
        x=t["Class"], y=t[col], marker=dict(color=[C.COLOR_MAP[c] for c in t["Class"]], cornerradius=6),
        text=[f"{v:,.2f}" for v in t[col]], textposition="outside", textfont=dict(color=P["text"], size=12),
        cliponaxis=False, hovertemplate="%{x}<br>%{y:,.2f} ha<extra></extra>"))
    fig.update_layout(yaxis_title="Area (ha)", yaxis_range=[0, max(float(t[col].max()) * 1.2, 1)], bargap=0.35)
    return T.style_fig(fig, C.CHART_H_MAIN, margin=dict(l=8, r=10, t=26, b=8))


def sankey_figure(geo: GeoData, idx: int, mode: str) -> tuple[go.Figure, str]:
    sel = geo.months[idx].name
    if mode == "baseline":
        tb, scol, dcol = geo.tbl_b, "Baseline class", "Destination class"
        vcol, frm = f"Base_{geo.months[idx].short}", geo.months[0].name
    else:
        tb, scol, dcol = geo.tbl_c, "PrevMon class", "CurrentMon class"
        vcol, frm = f"{geo.months[idx - 1].short}_{geo.months[idx].short}", geo.months[idx - 1].name

    t = tb[tb[vcol] > 0]
    rank = {c: i for i, c in enumerate(C.CLASS_ORDER)}
    n = len(C.CLASS_ORDER)
    src = [rank[s] for s in t[scol]]
    dst = [rank[d] + n for d in t[dcol]]
    link_col = ["rgba(111,208,140,0.55)" if rank[d] > rank[s] else "rgba(239,83,80,0.55)" if rank[d] < rank[s]
                else "rgba(160,175,168,0.32)" for s, d in zip(t[scol], t[dcol])]
    fig = go.Figure(go.Sankey(
        arrangement="snap", textfont=dict(color=P["text"], size=11.5, family=T.FONT_UI),
        node=dict(pad=18, thickness=16, line=dict(color="rgba(0,0,0,0.55)", width=0.5),
                  label=[f"{frm}: {c}" for c in C.CLASS_ORDER] + [f"{sel}: {c}" for c in C.CLASS_ORDER],
                  color=[C.COLOR_MAP[c] for c in C.CLASS_ORDER] * 2),
        link=dict(source=src, target=dst, value=t[vcol].tolist(), color=link_col,
                  hovertemplate="%{source.label} → %{target.label}<br>%{value:.2f} ha<extra></extra>")))
    fig.update_layout(annotations=[dict(
        text="<span style='color:#6fd08c'>■</span> improved   <span style='color:#ef5350'>■</span> declined   "
             "<span style='color:#a0afa8'>■</span> unchanged",
        xref="paper", yref="paper", x=0.5, y=1.035, showarrow=False, font=dict(size=11, color=P["muted"]))])
    T.style_fig(fig, C.CHART_H_MAIN, margin=dict(l=6, r=6, t=30, b=8))
    return fig, f"Sankey: {frm} → {sel}"


def stack_figure(geo: GeoData, idx: int) -> go.Figure:
    names = [m.name for m in geo.months]
    fig = go.Figure()
    for _, r in geo.tbl_a.iterrows():
        fig.add_trace(go.Bar(y=names, x=[r[f"{m.short}_area"] for m in geo.months], name=r["Class"], orientation="h",
                             marker_color=C.COLOR_MAP[r["Class"]],
                             hovertemplate="%{y} · " + r["Class"] + "<br>%{x:,.2f} ha<extra></extra>"))
    fig.update_layout(
        barmode="stack", showlegend=False, xaxis_title="Area (ha)", yaxis=dict(autorange="reversed"),
        shapes=[dict(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=idx - 0.5, y1=idx + 0.5,
                     line=dict(color=P["text"], width=2))])
    T.style_fig(fig, C.CHART_H_BOTTOM, margin=dict(l=8, r=10, t=4, b=30))
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return fig


def trend_figure(geo: GeoData, idx: int) -> go.Figure:
    names = [m.name for m in geo.months]
    fig = go.Figure(go.Scatter(x=names, y=geo.agb_total, mode="lines+markers", fill="tozeroy",
                               fillcolor="rgba(156,197,161,0.10)", line=dict(color=P["sage"], width=2.5),
                               marker=dict(size=7, color=P["sage"]),
                               hovertemplate="%{x}<br>%{y:,.2f} t C<extra></extra>"))
    fig.add_trace(go.Scatter(x=[names[idx]], y=[geo.agb_total[idx]], mode="markers", hoverinfo="skip",
                             marker=dict(size=15, color=P["green"], line=dict(width=2.5, color="#ffffff"))))
    fig.update_layout(showlegend=False, yaxis_title="t C", yaxis_rangemode="tozero")
    return T.style_fig(fig, C.CHART_H_BOTTOM, margin=dict(l=8, r=14, t=8, b=8))


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #
def _ticks(names: list[str], idx: int) -> str:
    return '<div class="ticks">' + "".join(f'<span class="{"on" if i == idx else ""}">{n}</span>'
                                           for i, n in enumerate(names)) + "</div>"


def render(geo: GeoData) -> None:
    names = [m.name for m in geo.months]
    # The slider lives further down the page; its current value is already in session_state at the
    # start of every rerun, so everything above it (KPIs, dropdown state) can use it.
    cur = st.session_state.get("sel_month", names[0])
    idx = names.index(cur) if cur in names else 0
    sel = names[idx]

    st.html(T.section_html(C.PANEL_TITLE, f"{names[0]} – {names[-1]} · Sentinel-2 NDVI (10 m) · IBM Granite AGB"))

    # ---- Row 1 : controls + KPIs  (raster dropdown above the map, Sankey dropdown above the Sankey) ----
    left, right = st.columns(C.MAIN_SPLIT)
    with left:
        c1, c2, c3 = st.columns([1.15, 1, 1])
        with c1, st.container(key="ctl_raster"):
            layer = st.selectbox("Raster layer (added to basemap)", list(C.LAYERS), format_func=C.LAYERS.get,
                                 key="raster_layer")
        c2.html(T.kpi_html("Harvested biomass (t C)", f"{geo.harvest_biomass[idx]:,.2f}", P["amber"],
                           "initial" if idx == 0 else sel))
        c3.html(T.kpi_html("Total AGB biomass (t C)", f"{geo.agb_total[idx]:,.2f}", P["green"], sel))
    with right, st.container(key="ctl_sankey"):
        mode = st.selectbox(
            "Sankey transition" if idx else "Sankey transition (from the second month)", list(SANKEY_MODES),
            format_func=lambda k: f"Baseline ({geo.months[0].short}) → selected month" if k == "baseline"
            else "Previous month → selected month", key="sankey_mode", disabled=(idx == 0))

    # ---- Row 2 : map (+ time scale) | Sankey ------------------------------------------------------
    left, right = st.columns(C.MAIN_SPLIT)
    with left, st.container(key="card_map"):
        st.html(T.card_header(C.LAYERS[layer], pill=sel))
        st.plotly_chart(map_figure(geo, layer, idx), key="map", config=MAP_CFG, theme=None)
        with st.container(key="slider_wrap"):
            st.html('<div class="tl-label">Time scale</div>')
            st.select_slider("Time scale", options=names, value=names[0], key="sel_month", label_visibility="collapsed")
            st.html(_ticks(names, idx))
    if st.session_state["sel_month"] != sel:       # safety net: keep everything in sync with the slider
        st.rerun()

    with right, st.container(key="card_sankey"):
        if idx == 0:
            st.html(T.card_header(f"Vegetation propagation area — {sel} (baseline)", pill="ha"))
            st.plotly_chart(baseline_bars(geo), key="sankey", config=GRAPH_CFG, theme=None)
        else:
            fig_s, title = sankey_figure(geo, idx, mode)
            st.html(T.card_header(title))
            st.plotly_chart(fig_s, key="sankey", config=GRAPH_CFG, theme=None)

    # ---- Row 3 : area stack | harvest-area + plot-area | biomass trend | legend --------------------
    b1, b2, b3, b4 = st.columns([4, 2, 4, 2])
    with b1, st.container(key="card_stack"):
        st.html(T.card_header("Vegetation propagation area (ha)"))
        st.plotly_chart(stack_figure(geo, idx), key="stack", config=GRAPH_CFG, theme=None)
    with b2:
        st.html(T.kpi_html("Harvest area (ha)", f"{geo.harvest_area[idx]:,.2f}", P["amber"], sel).replace('class="kpi"', 'class="kpi lg"'))
        st.html(T.kpi_html("Total plot area (ha)", f"{geo.plot_area_ha:,.2f}", P["sky"]).replace('class="kpi"', 'class="kpi lg"'))
    with b3, st.container(key="card_trend"):
        st.html(T.card_header("Total biomass trend (t C)"))
        st.plotly_chart(trend_figure(geo, idx), key="trend", config=GRAPH_CFG, theme=None)
    with b4, st.container(key="card_legend"):
        st.html(T.card_header("Legend"))
        st.html(T.legend_html(layer, geo.agb_range))

    st.html(f'<div class="foot">Demo data · Sentinel-2 L2A monthly median NDVI · IBM Granite geospatial biomass (HLS 30 m → {geo.res_m:.0f} m) · '
            f'carbon fraction {geo.carbon_fraction} · {geo.crs} · basemap: {C.BASEMAP_NAME} © Esri</div>')
