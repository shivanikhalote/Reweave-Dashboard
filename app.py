"""
Digital MRV for Community Invasive-Species Removal — Streamlit App
====================================================================
Run locally:
    pip install -r requirements.txt
    streamlit run app.py

See README.md for free cloud deployment steps (Streamlit Community Cloud).
"""

import os
import json
import tempfile
from datetime import date

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mrv_core import (
    MRVSystem, Plot, MonitoringEvent, TreeRecord, QuadratRecord,
    MonitoringPhase, LandUseType, SpeciesStatus, MeasurementMethod,
    SPECIES_DB, compute_biomass_summary, verify_event,
)

st.set_page_config(page_title="Community Invasive-Removal MRV", page_icon="🌱", layout="wide")

# ---------------------------------------------------------------------------
# Session state / persistence helpers
# ---------------------------------------------------------------------------

if "mrv" not in st.session_state:
    st.session_state.mrv = MRVSystem()

mrv: MRVSystem = st.session_state.mrv

TREE_SPECIES = {k: v for k, v in SPECIES_DB.items() if v.method == MeasurementMethod.TREE_CENSUS}
QUADRAT_SPECIES = {k: v for k, v in SPECIES_DB.items() if v.method == MeasurementMethod.QUADRAT_HARVEST}


def load_demo_data():
    """Populate session state with the worked example scenario."""
    from demo_run import build_scenario
    st.session_state.mrv = build_scenario()


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("🌱 Digital MRV")
st.sidebar.caption("Biomass monitoring for invasive removal on community plots")

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Register Plot", "Log Monitoring Event", "Reports & Charts", "Data Export / Import"],
)

st.sidebar.divider()
if st.sidebar.button("↺ Load demo scenario"):
    load_demo_data()
    st.sidebar.success("Demo data loaded.")
if st.sidebar.button("🗑 Reset all data"):
    st.session_state.mrv = MRVSystem()
    st.sidebar.warning("All data cleared.")

# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------

if page == "Dashboard":
    st.title("Dashboard")
    st.write(
        "Track biomass and land use across three monitoring phases for each "
        "community working plot: **before** invasive removal (baseline), "
        "**during** removal (clearing progress), and **after** removal "
        "(restoration outcomes)."
    )

    if not mrv.plots:
        st.info("No plots registered yet. Use **Register Plot** in the sidebar, "
                 "or click **Load demo scenario** to explore the app with sample data.")
    else:
        for pid, plot in mrv.plots.items():
            events = mrv.events_for_plot(pid)
            phases_logged = sorted({e.phase.value for e in events})
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.subheader(plot.name)
                c1.caption(f"Community: {plot.community_name}  •  Plot ID: {pid}")
                c2.metric("Area (ha)", plot.area_ha)
                c3.metric("Current land use", (plot.current_land_use.value.replace("_", " ")
                                                if plot.current_land_use else "—"))
                st.write(f"**Monitoring events logged:** {len(events)}  |  "
                         f"**Phases covered:** {', '.join(p.replace('_',' ') for p in phases_logged) or 'none'}")

# ---------------------------------------------------------------------------
# Page: Register Plot
# ---------------------------------------------------------------------------

elif page == "Register Plot":
    st.title("Register a Community Working Plot")

    plot_id = st.text_input("Plot ID (unique)", value=f"PLOT-{len(mrv.plots)+1:03d}")
    name = st.text_input("Plot name")
    community = st.text_input("Community / group name")
    area_ha = st.number_input("Area (hectares)", min_value=0.01, value=1.0, step=0.1)
    land_use = st.selectbox("Current land use", [lu.value for lu in LandUseType],
                              format_func=lambda v: v.replace("_", " "))
    lat = st.number_input("GPS latitude (optional)", value=0.0, format="%.6f")
    lon = st.number_input("GPS longitude (optional)", value=0.0, format="%.6f")
    survey_date = st.date_input("Land-use record date", value=date.today())

    if st.button("Register plot", type="primary"):
        if not plot_id or not name:
            st.error("Plot ID and name are required.")
        elif plot_id in mrv.plots:
            st.error(f"Plot ID '{plot_id}' already exists.")
        else:
            plot = Plot(
                plot_id=plot_id, name=name, community_name=community,
                area_ha=area_ha,
                gps_boundary=[(lat, lon)] if (lat or lon) else None,
            )
            plot.set_land_use(survey_date, LandUseType(land_use))
            mrv.register_plot(plot)
            st.success(f"Plot '{name}' registered.")

# ---------------------------------------------------------------------------
# Page: Log Monitoring Event
# ---------------------------------------------------------------------------

elif page == "Log Monitoring Event":
    st.title("Log a Monitoring Event")

    if not mrv.plots:
        st.warning("Register a plot first.")
        st.stop()

    plot_id = st.selectbox("Plot", list(mrv.plots.keys()),
                            format_func=lambda pid: f"{mrv.plots[pid].name} ({pid})")
    phase = st.selectbox("Monitoring phase", [p.value for p in MonitoringPhase],
                          format_func=lambda v: v.replace("_", " "))
    event_date = st.date_input("Survey date", value=date.today())
    monitor_name = st.text_input("Monitor / surveyor name")
    col1, col2 = st.columns(2)
    gps_lat = col1.number_input("GPS latitude", value=0.0, format="%.6f")
    gps_lon = col2.number_input("GPS longitude", value=0.0, format="%.6f")
    notes = st.text_area("Field notes")
    photos = st.file_uploader("Photo evidence", accept_multiple_files=True,
                               type=["jpg", "jpeg", "png"])

    biomass_removed_kg = None
    tree_records, quadrat_records = [], []

    if phase == MonitoringPhase.DURING_REMOVAL.value:
        st.subheader("Removal operation log")
        biomass_removed_kg = st.number_input("Biomass physically removed (kg)", min_value=0.0, step=10.0)
    else:
        st.subheader("Tree / shrub census (allometric method)")
        n_trees = st.number_input("Number of tree species entries", min_value=0, max_value=15,
                                   value=0, step=1, key="n_tree_rows")
        for i in range(int(n_trees)):
            c1, c2, c3, c4 = st.columns(4)
            sp = c1.selectbox(f"Species #{i+1}", list(TREE_SPECIES.keys()),
                               format_func=lambda k: TREE_SPECIES[k].common_name, key=f"tree_sp_{i}")
            cnt = c2.number_input("Count", min_value=1, value=1, step=1, key=f"tree_cnt_{i}")
            dbh = c3.number_input("Mean DBH (cm)", min_value=0.1, value=5.0, step=0.1, key=f"tree_dbh_{i}")
            ht = c4.number_input("Mean height (m, optional)", min_value=0.0, value=0.0, step=0.1, key=f"tree_ht_{i}")
            tree_records.append(TreeRecord(species_key=sp, count=int(cnt), mean_dbh_cm=dbh,
                                            mean_height_m=(ht or None)))

        st.subheader("Quadrat harvest sampling (herbaceous / shrub biomass)")
        n_quad = st.number_input("Number of quadrat entries", min_value=0, max_value=15,
                                  value=0, step=1, key="n_quad_rows")
        for i in range(int(n_quad)):
            c1, c2, c3 = st.columns(3)
            sp = c1.selectbox(f"Species #{i+1} ", list(QUADRAT_SPECIES.keys()),
                               format_func=lambda k: QUADRAT_SPECIES[k].common_name, key=f"quad_sp_{i}")
            fw = c2.number_input("Fresh weight (kg)", min_value=0.0, value=1.0, step=0.1, key=f"quad_fw_{i}")
            area = c3.number_input("Quadrat area (m²)", min_value=0.1, value=4.0, step=0.1, key=f"quad_area_{i}")
            quadrat_records.append(QuadratRecord(species_key=sp, fresh_weight_kg=fw, quadrat_area_m2=area))

    update_land_use = st.checkbox("Also update plot's current land use with this event")
    new_land_use = None
    if update_land_use:
        new_land_use = st.selectbox("New land use", [lu.value for lu in LandUseType],
                                     format_func=lambda v: v.replace("_", " "), key="new_lu")

    if st.button("Save monitoring event", type="primary"):
        event = MonitoringEvent(
            plot_id=plot_id,
            phase=MonitoringPhase(phase),
            event_date=event_date,
            monitor_name=monitor_name or "Unspecified",
            tree_records=tree_records,
            quadrat_records=quadrat_records,
            gps_point=(gps_lat, gps_lon) if (gps_lat or gps_lon) else None,
            photo_evidence=[p.name for p in photos] if photos else [],
            notes=notes,
            biomass_removed_kg=biomass_removed_kg,
        )
        summary = mrv.add_event(event)
        if update_land_use and new_land_use:
            mrv.plots[plot_id].set_land_use(event_date, LandUseType(new_land_use))

        st.success(f"Event saved (ID `{event.event_id}`).")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invasive AGB (t/ha)", summary.invasive_agb_t_ha)
        c2.metric("Native AGB (t/ha)", summary.native_agb_t_ha)
        c3.metric("Carbon stock (tC/ha)", summary.carbon_stock_tC_ha)
        c4.metric("CO2e (t/ha)", summary.co2e_t_ha)

        flags = verify_event(event)
        if flags:
            st.warning("Verification flags:\n" + "\n".join(f"- {f}" for f in flags))
        else:
            st.success("✅ No data-quality issues flagged.")

# ---------------------------------------------------------------------------
# Page: Reports & Charts
# ---------------------------------------------------------------------------

elif page == "Reports & Charts":
    st.title("Reports & Charts")

    if not mrv.plots:
        st.warning("Register a plot and log events first.")
        st.stop()

    plot_id = st.selectbox("Plot", list(mrv.plots.keys()),
                            format_func=lambda pid: f"{mrv.plots[pid].name} ({pid})")
    plot = mrv.plots[plot_id]
    comp = mrv.phase_comparison(plot_id)

    if not comp:
        st.info("No monitoring events logged for this plot yet.")
        st.stop()

    st.subheader("Phase summary (per hectare)")
    rows = []
    for phase_val, s in comp.items():
        rows.append({
            "Phase": phase_val.replace("_", " "),
            "Date": s.event_date,
            "Invasive AGB (t/ha)": s.invasive_agb_t_ha,
            "Native AGB (t/ha)": s.native_agb_t_ha,
            "Total AGB (t/ha)": s.total_agb_t_ha,
            "Carbon (tC/ha)": s.carbon_stock_tC_ha,
            "CO2e (t/ha)": s.co2e_t_ha,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    report = mrv.impact_report(plot_id)

    st.subheader("Removal & restoration impact")
    c1, c2, c3 = st.columns(3)
    c1.metric("Invasive biomass removed (logged)",
              f"{report['invasive_biomass_removed_during_ops_kg']:,.0f} kg")
    if "invasive_pct_reduction" in report and report["invasive_pct_reduction"] is not None:
        c2.metric("Invasive standing-biomass reduction", f"{report['invasive_pct_reduction']}%")
    if "net_co2e_change_t_ha" in report:
        c3.metric("Net CO2e change", f"{report['net_co2e_change_t_ha']} t/ha")

    # --- charts ---
    phase_order = [p for p in [MonitoringPhase.BASELINE.value, MonitoringPhase.DURING_REMOVAL.value,
                                MonitoringPhase.POST_REMOVAL.value, MonitoringPhase.FOLLOW_UP.value]
                   if p in comp]
    labels = [p.replace("_", " ") for p in phase_order]
    invasive_vals = [comp[p].invasive_agb_t_ha for p in phase_order]
    native_vals = [comp[p].native_agb_t_ha for p in phase_order]

    colA, colB = st.columns(2)
    with colA:
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.bar(labels, invasive_vals, label="Invasive AGB", color="#c0392b")
        ax.bar(labels, native_vals, bottom=invasive_vals, label="Native AGB", color="#27ae60")
        ax.set_ylabel("t/ha")
        ax.set_title("Biomass by phase")
        ax.legend()
        plt.xticks(rotation=15)
        st.pyplot(fig)

    with colB:
        carbon_vals = [comp[p].carbon_stock_tC_ha for p in phase_order]
        co2e_vals = [comp[p].co2e_t_ha for p in phase_order]
        x = range(len(labels))
        width = 0.35
        fig2, ax2 = plt.subplots(figsize=(5, 4))
        ax2.bar([i - width / 2 for i in x], carbon_vals, width, label="Carbon (tC/ha)", color="#34495e")
        ax2.bar([i + width / 2 for i in x], co2e_vals, width, label="CO2e (t/ha)", color="#2980b9")
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(labels, rotation=15)
        ax2.set_title("Carbon & CO2e by phase")
        ax2.legend()
        st.pyplot(fig2)

    st.subheader("Land-use history")
    for d, u in plot.land_use_history:
        st.write(f"- **{d}** — {u.value.replace('_',' ') if hasattr(u,'value') else str(u).replace('_',' ')}")

    st.subheader("Verification flags")
    any_flags = False
    for event in mrv.events_for_plot(plot_id):
        flags = verify_event(event)
        if flags:
            any_flags = True
            st.warning(f"Event `{event.event_id}` ({event.phase.value}): " + "; ".join(flags))
    if not any_flags:
        st.success("✅ No data-quality issues flagged across all events for this plot.")

# ---------------------------------------------------------------------------
# Page: Data Export / Import
# ---------------------------------------------------------------------------

elif page == "Data Export / Import":
    st.title("Data Export / Import")
    st.write(
        "This prototype keeps data in memory for the current session. "
        "Export a JSON snapshot to save your work, and import it later "
        "(or on another device) to continue."
    )

    st.subheader("Export")
    if mrv.plots:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mrv_data.json")
            mrv.to_json(path)
            with open(path, "rb") as f:
                st.download_button("⬇ Download mrv_data.json", f, file_name="mrv_data.json",
                                    mime="application/json")

        report_bundle = {pid: mrv.impact_report(pid) for pid in mrv.plots}
        st.download_button("⬇ Download impact report (JSON)",
                            json.dumps(report_bundle, indent=2, default=str),
                            file_name="mrv_impact_report.json", mime="application/json")
    else:
        st.info("Nothing to export yet.")

    st.subheader("Import")
    uploaded = st.file_uploader("Upload a previously exported mrv_data.json", type=["json"])
    if uploaded and st.button("Load uploaded data"):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "uploaded.json")
            with open(path, "wb") as f:
                f.write(uploaded.getbuffer())
            st.session_state.mrv = MRVSystem.from_json(path)
        st.success("Data imported.")
        st.rerun()
