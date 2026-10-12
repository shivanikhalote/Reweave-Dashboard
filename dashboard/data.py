"""Load the pre-processed outputs (GeoTIFFs + Excel + plot polygon) for the dashboard.

Nothing here re-runs the heavy Sentinel-2 / IBM Granite processing – it only reads the
files the notebook already wrote to `data/Outputs_VegProp_AGB/`.  Months are discovered
from the file names, so a new notebook run with different months works without code changes.
"""
from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, transform, transform_geom

from . import config as C

WEB_MERCATOR = "EPSG:3857"
WGS84 = "EPSG:4326"


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Month:
    code: str      # "Oct_2025"  (used in file names)
    short: str     # "Oct"       (used in Excel column names)
    name: str      # "Oct 2025"  (shown in the UI)


@dataclass
class GeoData:
    months: list[Month]
    tbl_a: pd.DataFrame
    tbl_b: pd.DataFrame
    tbl_c: pd.DataFrame
    tbl_d: pd.DataFrame
    plot_area_ha: float
    carbon_fraction: float
    crs: str
    res_m: float
    aoi_geojson: dict
    bbox_wgs: tuple[float, float, float, float]      # minx, miny, maxx, maxy
    center: tuple[float, float]                       # lon, lat
    agb_range: tuple[float, float]
    agb_total: list[float]
    harvest_biomass: list[float]
    harvest_area: list[float]
    overlays: dict[tuple[str, int], tuple[str, list]] = field(default_factory=dict)
    veg_arrays: list[np.ndarray] = field(default_factory=list)   # kept for validation
    logo_path: Path | None = None

    @property
    def pixel_ha(self) -> float:
        return (self.res_m * self.res_m) / 10_000.0


# --------------------------------------------------------------------------- #
# Months
# --------------------------------------------------------------------------- #
_VEG_RE = re.compile(r"VegPropagation_(?P<mon>[A-Za-z]{3})_(?P<year>\d{4})_")


def discover_months(data_dir: Path) -> list[Month]:
    veg_dir = data_dir / C.SUBDIRS["veg"]
    found = []
    for f in veg_dir.glob("VegPropagation_*.tif"):
        m = _VEG_RE.match(f.name)
        if m:
            code = f"{m['mon']}_{m['year']}"
            found.append((datetime.strptime(code, "%b_%Y"), Month(code, m["mon"], f"{m['mon']} {m['year']}")))
    if not found:
        raise FileNotFoundError(f"No VegPropagation_*.tif files found in {veg_dir}")
    return [mo for _, mo in sorted(found, key=lambda t: t[0])]


# --------------------------------------------------------------------------- #
# Rasters
# --------------------------------------------------------------------------- #
def read_raster(path: Path):
    """Read band 1 as float32 with NaN for no-data (uint8 class rasters use 255)."""
    with rasterio.open(path) as ds:
        arr = ds.read(1).astype("float32")
        nod = ds.nodata
        if nod is not None and not np.isnan(nod):
            arr[arr == nod] = np.nan
        return arr, ds.transform, ds.crs


def _find_raster(data_dir: Path, layer: str, code: str) -> Path:
    folder = data_dir / C.SUBDIRS[layer]
    hits = sorted(folder.glob(C.RASTER_PATTERNS[layer].format(code=code)))
    if not hits:
        raise FileNotFoundError(f"Missing {layer} raster for {code} in {folder}")
    return hits[0]


# --------------------------------------------------------------------------- #
# Plot polygon (the notebook's AOI) – Esri JSON *or* GeoJSON -> GeoJSON (WGS84)
# --------------------------------------------------------------------------- #
def _ring_area(ring) -> float:
    """Signed shoelace area: >0 counter-clockwise, <0 clockwise."""
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:]))


def _esri_rings_to_geometry(rings) -> dict:
    polys: list[list] = []
    for ring in rings:
        if len(ring) < 4 or abs(_ring_area(ring)) < 1e-18:
            continue
        if _ring_area(ring) < 0:                 # Esri outer rings are clockwise
            polys.append([ring[::-1]])           # -> GeoJSON outer ring = counter-clockwise
        elif polys:                              # counter-clockwise = hole
            polys[-1].append(ring[::-1])
        else:
            polys.append([ring])
    if not polys:
        raise ValueError("The plot file contains no usable polygon rings")
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def _iter_coords(geom):
    def walk(c):
        if c and isinstance(c[0], (int, float)):
            yield c
        else:
            for part in c:
                yield from walk(part)
    yield from walk(geom["coordinates"])


def _is_esri(obj: dict) -> bool:
    """True for ArcGIS REST 'Esri JSON' (features carry `attributes` + `geometry.rings`)."""
    if str(obj.get("geometryType", "")).startswith("esriGeometry"):
        return True
    feats = obj.get("features") or []
    return bool(feats) and isinstance(feats[0].get("geometry"), dict) and "rings" in feats[0]["geometry"]


def load_aoi(data_dir: Path) -> dict:
    path = next((data_dir / n for n in C.AOI_CANDIDATES if (data_dir / n).exists()), None)
    if path is None:
        raise FileNotFoundError(f"None of {C.AOI_CANDIDATES} found in {data_dir}")
    obj = json.loads(path.read_text())

    if _is_esri(obj):
        sref = obj.get("spatialReference") or {}
        wkid = sref.get("latestWkid") or sref.get("wkid")
        feats = []
        for f in obj["features"]:
            if "rings" not in (f.get("geometry") or {}):
                raise ValueError("Only polygon geometries are supported for the plot boundary")
            geom = _esri_rings_to_geometry(f["geometry"]["rings"])
            if wkid and int(wkid) not in (4326,):
                src = {102100: 3857, 102113: 3857}.get(int(wkid), int(wkid))
                geom = transform_geom(f"EPSG:{src}", WGS84, geom)
            feats.append({"type": "Feature", "properties": f.get("attributes", {}), "geometry": geom})
        return {"type": "FeatureCollection", "features": feats}

    # plain GeoJSON
    if obj.get("type") == "FeatureCollection":
        return obj
    if obj.get("type") == "Feature":
        return {"type": "FeatureCollection", "features": [obj]}
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": obj}]}


def aoi_bounds(fc: dict) -> tuple[float, float, float, float]:
    pts = [p for f in fc["features"] for p in _iter_coords(f["geometry"])]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))


# --------------------------------------------------------------------------- #
# Map overlays  (same recipe as the notebook's make_overlay)
# --------------------------------------------------------------------------- #
def _veg_lut() -> np.ndarray:
    return np.array([[int(c * 255) for c in mcolors.to_rgb(C.COLOR_MAP[C.CLASS_MAP[k]])] for k in range(4)], dtype=np.uint8)


def _rgba(layer: str, arr: np.ndarray, agb_range: tuple[float, float]) -> np.ndarray:
    nan = np.isnan(arr)
    if layer == "veg":
        rgb = _veg_lut()[np.nan_to_num(arr, nan=0).astype(int).clip(0, 3)]
    else:
        if layer == "ndvi":
            vmin, vmax, cm = C.NDVI_VMIN, C.NDVI_VMAX, matplotlib.colormaps[C.CMAP_NDVI]
        else:
            (vmin, vmax), cm = agb_range, matplotlib.colormaps[C.CMAP_AGB]
        t = np.nan_to_num((arr - vmin) / (vmax - vmin), nan=0).clip(0, 1)
        rgb = (cm(t)[..., :3] * 255).astype(np.uint8)
    return np.dstack([rgb, np.where(nan, 0, 255).astype(np.uint8)])


def make_overlay(layer: str, arr: np.ndarray, src_transform, src_crs, agb_range) -> tuple[str, list]:
    """Reproject to Web Mercator, colour-map to a PNG data-URI and return its 4 corner lon/lat."""
    h, w = arr.shape
    left, bottom, right, top = array_bounds(h, w, src_transform)
    dst_tr, dw, dh = calculate_default_transform(src_crs, WEB_MERCATOR, w, h, left=left, bottom=bottom, right=right, top=top)
    dst = np.full((dh, dw), np.nan, dtype="float32")
    reproject(source=arr, destination=dst, src_transform=src_transform, src_crs=src_crs, src_nodata=np.nan,
              dst_transform=dst_tr, dst_crs=WEB_MERCATOR, dst_nodata=np.nan, resampling=Resampling.nearest)
    west, south, east, north = array_bounds(dh, dw, dst_tr)

    rgba = _rgba(layer, dst, agb_range)
    k = int(np.clip(np.ceil(640 / max(rgba.shape[:2])), 1, 40))          # crisp pixels on tiny plots
    if k > 1:
        rgba = np.repeat(np.repeat(rgba, k, 0), k, 1)
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    (lon_w, lon_e), (lat_n, lat_s) = transform(WEB_MERCATOR, WGS84, [west, east], [north, south])
    return uri, [[lon_w, lat_n], [lon_e, lat_n], [lon_e, lat_s], [lon_w, lat_s]]


# --------------------------------------------------------------------------- #
# Main loader
# --------------------------------------------------------------------------- #
def _need(df: pd.DataFrame, cols: list[str], sheet: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Sheet '{sheet}' is missing columns {missing}; found {list(df.columns)}")


def load_geodata(data_dir: Path | str = C.DATA_DIR) -> GeoData:
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data folder not found: {data_dir}")

    months = discover_months(data_dir)
    n = len(months)

    # ---- Excel tables ---------------------------------------------------- #
    sheets = pd.read_excel(data_dir / C.TABLES_FILE, sheet_name=None)
    tbl_a, tbl_b, tbl_c = sheets[C.SHEET_A], sheets[C.SHEET_B], sheets[C.SHEET_C]
    tbl_d, info = sheets[C.SHEET_D], sheets[C.SHEET_INFO]
    _need(tbl_a, ["Class"] + [f"{m.short}_area" for m in months], C.SHEET_A)
    _need(tbl_b, ["Baseline class", "Destination class"] + [f"Base_{m.short}" for m in months[1:]], C.SHEET_B)
    _need(tbl_c, ["PrevMon class", "CurrentMon class"] + [f"{months[i-1].short}_{months[i].short}" for i in range(1, n)], C.SHEET_C)
    _need(tbl_d, ["month", "Total AGB Biomass (t C)", "Harvested Biomass (t C)", "Harvested Area (ha)"], C.SHEET_D)

    kv = dict(zip(info["Item"], info["Value"]))
    plot_area = float(kv["Total plot area (ha)"])
    carbon = float(kv.get("Carbon fraction", 0.47))
    crs = str(kv.get("CRS", "EPSG:32646"))
    res_m = float(kv.get("Pixel size (m)", 10))

    d = tbl_d.assign(_k=tbl_d["month"].astype(str).str.upper()).set_index("_k")
    keys = [m.short.upper() for m in months]
    if not set(keys).issubset(d.index):
        raise ValueError(f"Table D months {list(d.index)} do not match raster months {keys}")
    agb_total = [float(d.loc[k, "Total AGB Biomass (t C)"]) for k in keys]
    hv_bio = [float(d.loc[k, "Harvested Biomass (t C)"]) for k in keys]
    hv_area = [float(d.loc[k, "Harvested Area (ha)"]) for k in keys]

    # ---- Plot polygon ---------------------------------------------------- #
    aoi = load_aoi(data_dir)
    bbox = aoi_bounds(aoi)
    center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

    # ---- Rasters (AOI-clipped, 10 m, UTM) -------------------------------- #
    arrays: dict[str, list[np.ndarray]] = {k: [] for k in ("agb", "ndvi", "veg")}
    geo_ref = {}
    for layer in arrays:
        for m in months:
            arr, tr, rcrs = read_raster(_find_raster(data_dir, layer, m.code))
            arrays[layer].append(arr)
            geo_ref[layer] = (tr, rcrs)
    shapes = {a.shape for lst in arrays.values() for a in lst}
    if len(shapes) != 1:
        raise ValueError(f"Rasters are not on a common grid: {shapes}")

    vmin, vmax = float(C.AGB_VMIN), float(C.AGB_VMAX)      # fixed scale (see config.EASY SETTINGS)

    overlays = {}
    for layer in arrays:
        tr, rcrs = geo_ref[layer]
        for i in range(n):
            overlays[(layer, i)] = make_overlay(layer, arrays[layer][i], tr, rcrs, (vmin, vmax))

    logo = data_dir / C.LOGO_FILE
    return GeoData(
        months=months, tbl_a=tbl_a, tbl_b=tbl_b, tbl_c=tbl_c, tbl_d=tbl_d,
        plot_area_ha=plot_area, carbon_fraction=carbon, crs=crs, res_m=res_m,
        aoi_geojson=aoi, bbox_wgs=bbox, center=center, agb_range=(vmin, vmax),
        agb_total=agb_total, harvest_biomass=hv_bio, harvest_area=hv_area,
        overlays=overlays, veg_arrays=arrays["veg"], logo_path=logo if logo.exists() else None,
    )
