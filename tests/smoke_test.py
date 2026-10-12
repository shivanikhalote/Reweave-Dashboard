"""Smoke test:  python tests/smoke_test.py   (run from the repo root, no pytest needed).

1. Re-computes Excel Tables A-D from the GeoTIFFs and checks they agree (guards against stale/mismatched outputs).
2. Runs the Streamlit app headlessly across every month x Sankey mode x raster layer and checks for exceptions.
"""
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from dashboard import config as C                      # noqa: E402
from dashboard.data import load_geodata, read_raster, _find_raster   # noqa: E402

g = load_geodata()
P, CF, veg = g.pixel_ha, g.carbon_fraction, g.veg_arrays
agb = [read_raster(_find_raster(C.DATA_DIR, "agb", m.code))[0] for m in g.months]
bad = []

def chk(label, calc, xl):
    if abs(calc - xl) > 0.006:
        bad.append(f"{label}: raster={calc} excel={xl}")

for ci, cn in C.CLASS_MAP.items():
    for i, m in enumerate(g.months):
        chk(f"A {cn} {m.short}", round(float((veg[i] == ci).sum()) * P, 2), float(g.tbl_a.loc[g.tbl_a['Class'] == cn, f"{m.short}_area"].iloc[0]))
for i in range(1, len(g.months)):
    for s, sn in C.CLASS_MAP.items():
        for d, dn in C.CLASS_MAP.items():
            col = f"{g.months[i-1].short}_{g.months[i].short}"
            chk(f"C {col} {sn}>{dn}", round(float(((veg[i-1] == s) & (veg[i] == d)).sum()) * P, 2),
                float(g.tbl_c[(g.tbl_c['PrevMon class'] == sn) & (g.tbl_c['CurrentMon class'] == dn)][col].iloc[0]))
            col = f"Base_{g.months[i].short}"
            chk(f"B {col} {sn}>{dn}", round(float(((veg[0] == s) & (veg[i] == d)).sum()) * P, 2),
                float(g.tbl_b[(g.tbl_b['Baseline class'] == sn) & (g.tbl_b['Destination class'] == dn)][col].iloc[0]))
for i, m in enumerate(g.months):
    chk(f"D total {m.short}", round(float(np.nansum(agb[i])) * P * CF, 2), g.agb_total[i])
    if i:
        mask = (veg[i-1] == 1) & (veg[i] == 0)
        chk(f"D harvest bio {m.short}", round(float(np.nansum(np.where(mask, agb[i-1] - agb[i], np.nan))) * P * CF, 2), g.harvest_biomass[i])
        chk(f"D harvest area {m.short}", round(float(mask.sum()) * P, 2), g.harvest_area[i])
print("data check:", "OK - Excel tables match the rasters" if not bad else "MISMATCH\n  " + "\n  ".join(bad[:10]))

from streamlit.testing.v1 import AppTest              # noqa: E402
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
assert not at.exception, [e.value for e in at.exception]
names = at.select_slider(key="sel_month").options
runs = 0
for layer in C.LAYERS:
    at.selectbox(key="raster_layer").set_value(layer).run()
    for nm in names:
        for mode in ("baseline", "previous"):
            at.select_slider(key="sel_month").set_value(nm).run()
            if not at.selectbox(key="sankey_mode").disabled:
                at.selectbox(key="sankey_mode").set_value(mode).run()
            assert not at.exception, (layer, nm, mode, [e.value for e in at.exception])
            runs += 1
print(f"app check: OK - {runs} month/mode/layer combinations ran without exceptions")
sys.exit(1 if bad else 0)
