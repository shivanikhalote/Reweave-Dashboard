# REWEAVE · Barnadi Grassland — Monitoring Dashboard (demo)

Streamlit dashboard for the **Barnadi grassland, Udalguri (Assam)** demo plot, with three panels:

| Panel | Status |
|---|---|
| **Geospatial** | Live. Vegetation propagation + above-ground biomass (AGB), from the pre-processed outputs in `data/` |
| **Community** | Empty placeholder (no data yet) |
| **Finance** | Empty placeholder (no data yet) |

The Geospatial panel reproduces the dashboard from the notebook `Combined_VegProp_AGB_Dashboard.ipynb`
(raster-layer dropdown + map + time slider, Sankey / baseline bars, KPIs, area stack, biomass trend, legend).
No heavy processing runs in the app; it only reads files the notebook already produced.

## Repository layout

```
app.py                      entry point (header, 3 tabs)
dashboard/
  config.py                 names, colours, class definitions, layout sizes
  data.py                   loads Excel tables, GeoTIFFs, plot polygon; builds map overlays
  geospatial.py             the Geospatial panel
  theme.py                  dark CSS, Plotly styling, logo helpers
data/Outputs_VegProp_AGB/   all notebook outputs (same folder structure the notebook writes)
  1_NDVI/ 2_VegetationPropagation/ 3_ChangeDetection_Baseline/ 4_ChangeDetection_MonthToMonth/
  5_AGB_10m_AOI/ 5_AGB_native30m_bbox/
  VegProp_AGB_Area_Biomass_Tables.xlsx   (sheets A, B, C, D, Plot_Info, Legend)
  Grassland_plot.json       plot boundary (Esri JSON; GeoJSON also accepted)
  reweave_logo.png
tests/smoke_test.py         checks Excel vs rasters, and runs the app headlessly
.streamlit/config.toml      dark theme
requirements.txt            pinned (numpy==2.2.6)
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
python tests/smoke_test.py                              # optional check
```

Tested on Python 3.12 and 3.13 with `numpy==2.2.6`.

## Redeploy on Streamlit Community Cloud

**Replace the existing app's code (keeps your URL):**
1. In your existing repo, delete the old app files and copy in everything from this folder (including `data/`, `.streamlit/`, `dashboard/`).
2. `git add -A && git commit -m "New 3-panel dashboard" && git push`
3. Streamlit Cloud redeploys automatically. Make sure the app's **Main file path** is `app.py`.
   If dependencies don't refresh, use *Manage app → Reboot app*.
4. Python 3.12 or 3.13 is recommended (Advanced settings → Python version; it can only be set when the app is created).

**Or deploy as a new app:** push this folder to a new GitHub repo → share.streamlit.io → *New app* → main file `app.py`.

The data folder is under 0.5 MB, so no Git LFS is needed.

## Updating the data

Re-run the notebook, then overwrite `data/Outputs_VegProp_AGB/` with its output folder (same names).
Months are discovered from the `VegPropagation_<Mon>_<Year>_*.tif` file names, so adding months needs no code change.
To use another folder, set the `REWEAVE_DATA_DIR` environment variable. Run `python tests/smoke_test.py` afterwards.

## Notes

- `streamlit` and `plotly` are pinned exactly because the styling relies on Streamlit's page structure; re-test before upgrading.
- The map basemap is **Esri World Imagery** (satellite imagery; `BASEMAP_NAME`/`BASEMAP_URL` in `dashboard/config.py`), fetched by the viewer's browser. Fonts (Manrope, Fraunces) load from Google Fonts with system fallbacks.
- Class definitions, colours and colour scales come from the notebook CONFIG (see `dashboard/config.py`).
