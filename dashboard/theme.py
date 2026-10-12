"""Dark theme: global CSS, Plotly styling, logo handling and small HTML builders."""
from __future__ import annotations

import base64
import io
from pathlib import Path
from string import Template

import matplotlib
import matplotlib.colors as mcolors
import numpy as np
import plotly.graph_objects as go
from PIL import Image

from . import config as C

P = C.PALETTE
FONT_UI = "'Manrope', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
FONT_DISPLAY = "'Fraunces', Georgia, 'Times New Roman', serif"


# --------------------------------------------------------------------------- #
# Logo
# --------------------------------------------------------------------------- #
def emblem_image(path: Path | None) -> Image.Image | None:
    """Crop the circular emblem out of the logo (drops transparent margins and the tiny wordmark)."""
    if path is None or not Path(path).exists():
        return None
    im = Image.open(path).convert("RGBA")
    alpha = np.array(im)[..., 3]
    filled = (alpha > 20).sum(axis=1) > 0
    bands, start = [], None
    for y, f in enumerate(filled):
        if f and start is None:
            start = y
        if not f and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, len(filled) - 1))
    bottom = bands[-2][1] if len(bands) > 1 else bands[-1][1]      # emblem = everything above the last text band
    ys, xs = np.where(alpha[: bottom + 1] > 20)
    return im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, bottom + 1))


def image_to_data_uri(im: Image.Image, max_px: int = 220) -> str:
    im = im.copy()
    im.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# --------------------------------------------------------------------------- #
# Global CSS
# --------------------------------------------------------------------------- #
_CSS = Template(r"""
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap');

:root{
  --bg:$bg; --surface:$surface; --card:$card; --border:$border; --text:$text; --muted:$muted;
  --sage:$sage; --beige:$beige; --green:$green; --amber:$amber; --sky:$sky;
}

/* ---------- base ---------- */
.stApp{
  background:
    radial-gradient(1100px 520px at 6% -12%, rgba(156,197,161,.11), transparent 62%),
    radial-gradient(900px 500px at 104% -6%, rgba(217,207,163,.07), transparent 58%),
    var(--bg);
  color:var(--text);
  font-family:$font_ui;
}
.stApp p, .stApp label, .stApp li, .stApp button, .stApp input, .stApp textarea{ font-family:$font_ui; }
[data-testid="stHeader"]{ background:transparent; }
[data-testid="stDecoration"], footer, #MainMenu{ visibility:hidden; height:0; }
[data-testid="stMainBlockContainer"], .block-container{
  padding:.7rem 1.5rem .6rem 1.5rem !important; max-width:100% !important;
}
[data-testid="stVerticalBlock"]{ gap:.5rem; }
[data-testid="stHorizontalBlock"]{ gap:.6rem; }

/* ---------- header ---------- */
.hdr{ display:flex; align-items:center; gap:14px; height:54px; }
.hdr-logo{ height:50px; width:auto; filter:drop-shadow(0 0 10px rgba(156,197,161,.28)); }
.hdr-text{ display:flex; flex-direction:column; line-height:1.12; }
.hdr-org{ font-size:10.5px; letter-spacing:.24em; text-transform:uppercase; color:var(--beige); font-weight:700; }
.hdr-name{ font-family:$font_display; font-size:26px; font-weight:600; color:var(--text); letter-spacing:.005em; }
.hdr-loc{ font-size:12px; color:var(--muted); font-weight:500; margin-left:10px; letter-spacing:.04em; }
.hdr-name-row{ display:flex; align-items:baseline; }
.chip{ margin-left:14px; padding:3px 10px; border-radius:999px; font-size:10px; font-weight:700; letter-spacing:.14em;
       color:var(--amber); border:1px solid rgba(242,180,90,.38); background:rgba(242,180,90,.08); align-self:center; }

/* ---------- tabs (pulled up into the header band, right-aligned) ---------- */
[data-testid="stTabs"]{ position:relative; }
[data-testid="stTabs"] [role="tablist"]{
  position:absolute; top:-59px; right:0; z-index:5; gap:4px; padding:4px; width:auto;
  background:rgba(255,255,255,.035); border:1px solid var(--border) !important; border-radius:14px;
}
[data-testid="stTabs"] [role="tablist"] > div:not([role="tab"]){ display:none; }
[data-testid="stTabs"] [role="tab"]{
  height:36px; padding:0 18px; border-radius:10px; background:transparent; color:var(--muted);
  transition:all .18s ease; cursor:pointer; display:flex; align-items:center; border:0;
}
[data-testid="stTabs"] [role="tab"] > div:not([data-testid="stMarkdownContainer"]){ display:none; }
[data-testid="stTabs"] [role="tab"] p{ font-size:13.5px; font-weight:700; letter-spacing:.03em; color:inherit; margin:0; }
[data-testid="stTabs"] [role="tab"]:hover{ color:var(--text); background:rgba(255,255,255,.05); }
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{
  color:#0a100d; background:linear-gradient(180deg,var(--sage),#86b48d); box-shadow:0 4px 14px rgba(156,197,161,.28);
}
[data-testid="stTabs"] [role="tabpanel"]{ padding-top:.1rem; }

/* ---------- cards ---------- */
[class*="st-key-card_"]{
  background:linear-gradient(180deg, rgba(255,255,255,.028), rgba(255,255,255,.008)), var(--card);
  border:1px solid var(--border); border-radius:14px; padding:${pad}px;
  box-shadow:0 10px 28px rgba(0,0,0,.30), inset 0 1px 0 rgba(255,255,255,.03);
  gap:6px !important; overflow:hidden; flex:0 0 auto !important;
}
.st-key-card_map, .st-key-card_sankey{ height:${h_main}px; }
.st-key-card_stack, .st-key-card_trend, .st-key-card_legend{ height:${h_bottom}px; }
.card-h{ display:flex; align-items:center; justify-content:space-between; height:${head}px; padding:0 4px; }
.card-h-t{ font-size:13px; font-weight:700; color:var(--text); letter-spacing:.02em; }
.card-h-pill{ font-size:10.5px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--sage);
              border:1px solid rgba(156,197,161,.35); background:rgba(156,197,161,.08); padding:2px 9px; border-radius:999px; }

/* ---------- control cards (dropdowns) + KPI cards share one look ---------- */
[class*="st-key-ctl_"], .kpi{
  height:${h_ctl}px; border:1px solid var(--border); border-radius:14px; padding:9px 14px 8px 14px;
  background:linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.01)), var(--card);
  box-shadow:0 8px 22px rgba(0,0,0,.26), inset 0 1px 0 rgba(255,255,255,.03);
  position:relative; overflow:hidden;
}
.kpi::before{ content:""; position:absolute; left:0; top:12px; bottom:12px; width:3px; border-radius:0 3px 3px 0; background:var(--accent,var(--sage)); }
.kpi-l{ font-size:10.5px; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.kpi-v{ margin-top:3px; font-size:27px; font-weight:700; line-height:1.1; color:var(--text); font-variant-numeric:tabular-nums; letter-spacing:-.01em; }
.kpi.lg{ height:${h_kpi_lg}px; padding-top:18px; margin-bottom:10px; }
.kpi.lg .kpi-v{ font-size:34px; margin-top:6px; }
.kpi-n{ margin-left:8px; font-size:11px; font-weight:600; color:var(--accent,var(--sage)); letter-spacing:.06em; text-transform:uppercase; }
[class*="st-key-ctl_"]{ gap:0 !important; flex:0 0 auto !important; padding-top:6px !important; padding-bottom:5px !important; }
[class*="st-key-ctl_"] [data-testid="stSelectbox"]{ margin-top:-2px; }
[class*="st-key-ctl_"] [data-testid="stWidgetLabel"]{ min-height:0; margin-bottom:2px; }
[data-testid="stWidgetLabel"] p{ font-size:10.5px !important; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color:var(--muted) !important; }
[data-testid="stSelectbox"] [role="group"]{ background:rgba(255,255,255,.045) !important; border:1px solid var(--border) !important;
  border-radius:9px !important; min-height:34px !important; height:34px !important; }
[data-testid="stSelectbox"] [role="group"]:hover{ border-color:rgba(156,197,161,.45) !important; }
[data-testid="stSelectbox"] input[role="combobox"], [data-testid="stSelectbox"] [role="group"] *{ font-size:13px; font-weight:600; }

/* ---------- time slider ---------- */
.st-key-slider_wrap{ padding:0 14px; }
.st-key-slider_wrap [data-testid="stTickBarMin"], .st-key-slider_wrap [data-testid="stTickBarMax"],
.st-key-slider_wrap [data-testid="stSliderTickBarMin"], .st-key-slider_wrap [data-testid="stSliderTickBarMax"],
.st-key-slider_wrap [data-testid="stSliderTickBar"]{ display:none; }
.ticks{ display:flex; justify-content:space-between; margin:-6px 4px 0 4px; }
.ticks span{ font-size:11px; font-weight:600; color:var(--muted); letter-spacing:.03em; }
.ticks span.on{ color:var(--sage); }
.tl-label{ font-size:10.5px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); padding:2px 18px 0 18px; }

/* ---------- legend ---------- */
.lg{ padding:2px 6px; }
.lg-title{ font-size:11.5px; font-weight:700; color:var(--text); margin-bottom:6px; }
.lg-bar{ height:12px; border-radius:4px; box-shadow:inset 0 0 0 1px rgba(255,255,255,.12); }
.lg-mm{ display:flex; justify-content:space-between; font-size:11px; color:var(--muted); margin-top:3px; font-variant-numeric:tabular-nums; }
.lg-item{ display:flex; align-items:center; font-size:11.5px; color:var(--text); margin:3px 0; }
.lg-box{ display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:8px; box-shadow:inset 0 0 0 1px rgba(255,255,255,.14); flex:none; }
.lg-note{ font-size:10.5px; color:var(--muted); margin-top:6px; line-height:1.35; }
.lg-sep{ height:1px; background:var(--border); margin:9px 0 6px 0; }
.lg-sub{ font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); font-weight:700; margin-bottom:3px; }
.lg-grid{ display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); column-gap:8px; }
.lg-grid .lg-item{ white-space:nowrap; font-size:11px; }

/* ---------- misc ---------- */
.section{ display:flex; align-items:center; justify-content:space-between; margin:2px 2px 0 2px; }
.section-t{ font-size:11px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; color:var(--beige); }
.section-s{ font-size:11px; color:var(--muted); letter-spacing:.03em; }
.foot{ margin-top:2px; font-size:10.5px; color:#6d8276; letter-spacing:.02em; text-align:center; }
.empty{ height:calc(100vh - 120px); min-height:430px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:10px;
        border:1.5px dashed rgba(141,163,150,.28); border-radius:18px; background:rgba(255,255,255,.012); }
.empty-ring{ width:64px; height:64px; border-radius:50%; border:2px solid rgba(156,197,161,.35); display:flex; align-items:center; justify-content:center; }
.empty-dot{ width:12px; height:12px; border-radius:50%; background:var(--sage); opacity:.7; animation:pulse 2.4s ease-in-out infinite; }
@keyframes pulse{ 0%,100%{ transform:scale(.7); opacity:.35 } 50%{ transform:scale(1.15); opacity:.85 } }
.empty-t{ font-family:$font_display; font-size:24px; color:var(--text); }
.empty-s{ font-size:13px; color:var(--muted); letter-spacing:.04em; }

/* plotly containers: no extra chrome */
[data-testid="stPlotlyChart"]{ border-radius:10px; }
""")


def css() -> str:
    return "<style>" + _CSS.substitute(
        bg=P["bg"], surface=P["surface"], card=P["card"], border=P["border"], text=P["text"], muted=P["muted"],
        sage=P["sage"], beige=P["beige"], green=P["green"], amber=P["amber"], sky=P["sky"],
        font_ui=FONT_UI, font_display=FONT_DISPLAY,
        pad=C.CARD_PAD, head=C.CARD_HEAD, h_main=C.H_MAIN, h_bottom=C.H_BOTTOM, h_ctl=C.H_CTL,
        h_kpi_lg=(C.H_BOTTOM - 10) // 2,
    ) + "</style>"


# --------------------------------------------------------------------------- #
# HTML builders  (single-line, no indentation -> never parsed as markdown code)
# --------------------------------------------------------------------------- #
def header_html(logo_uri: str | None) -> str:
    logo = f'<img class="hdr-logo" src="{logo_uri}" alt="REWEAVE logo">' if logo_uri else ""
    return (f'<div class="hdr">{logo}<div class="hdr-text">'
            f'<div class="hdr-org">{C.ORG_NAME}</div>'
            f'<div class="hdr-name-row"><span class="hdr-name">{C.LANDSCAPE}</span><span class="hdr-loc">{C.LOCATION}</span></div>'
            f'</div><span class="chip">DEMO</span></div>')


def section_html(title: str, sub: str) -> str:
    return f'<div class="section"><div class="section-t">{title}</div><div class="section-s">{sub}</div></div>'


def card_header(title: str, pill: str | None = None) -> str:
    pill_html = f'<span class="card-h-pill">{pill}</span>' if pill else ""
    return f'<div class="card-h"><span class="card-h-t">{title}</span>{pill_html}</div>'


def kpi_html(label: str, value: str, accent: str, note: str = "") -> str:
    n = f'<span class="kpi-n">{note}</span>' if note else ""
    return f'<div class="kpi" style="--accent:{accent}"><div class="kpi-l">{label}</div><div class="kpi-v">{value}{n}</div></div>'


def _grad(cmap: str) -> str:
    cm = matplotlib.colormaps[cmap]
    return ", ".join(mcolors.to_hex(cm(t)) for t in np.linspace(0, 1, 6))


_SHORT = {"Non-Vegetation": "Non-veg.", "Sparse Vegetation": "Sparse", "Moderate Vegetation": "Moderate", "Dense Vegetation": "Dense"}


def _class_items(compact: bool = False) -> str:
    items = "".join(
        f'<div class="lg-item"><span class="lg-box" style="background:{C.COLOR_MAP[c]}"></span>{_SHORT[c] if compact else c}</div>'
        for c in C.CLASS_ORDER)
    return f'<div class="lg-grid">{items}</div>' if compact else items


def legend_html(layer: str, agb_range: tuple[float, float]) -> str:
    if layer == "veg":
        return (f'<div class="lg"><div class="lg-title">Vegetation propagation</div>{_class_items()}'
                f'<div class="lg-note">{C.NDVI_BREAKS_TEXT}</div></div>')
    if layer == "ndvi":
        title, cmap, lo, hi = "NDVI", C.CMAP_NDVI, C.NDVI_VMIN, C.NDVI_VMAX
    else:
        title, cmap, (lo, hi) = "AGB (Mg/ha)", C.CMAP_AGB, agb_range
    return (f'<div class="lg"><div class="lg-title">{title}</div>'
            f'<div class="lg-bar" style="background:linear-gradient(to right, {_grad(cmap)})"></div>'
            f'<div class="lg-mm"><span>{lo:.2f}</span><span>{hi:.2f}</span></div>'
            f'<div class="lg-sep"></div><div class="lg-sub">Classes (charts)</div>{_class_items(compact=True)}</div>')


def empty_html(title: str, sub: str) -> str:
    return (f'<div class="empty"><div class="empty-ring"><div class="empty-dot"></div></div>'
            f'<div class="empty-t">{title}</div><div class="empty-s">{sub}</div></div>')


# --------------------------------------------------------------------------- #
# Plotly dark styling
# --------------------------------------------------------------------------- #
def style_fig(fig: go.Figure, height: int, margin: dict | None = None) -> go.Figure:
    fig.update_layout(
        height=height, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_UI, size=11, color=P["text"]),
        margin=margin or dict(l=8, r=10, t=8, b=8),
        hoverlabel=dict(bgcolor="#0e1712", bordercolor=P["border"], font=dict(color=P["text"], family=FONT_UI, size=12)),
    )
    fig.update_xaxes(gridcolor=P["grid"], zerolinecolor=P["grid"], linecolor=P["grid"], tickfont=dict(color=P["muted"]))
    fig.update_yaxes(gridcolor=P["grid"], zerolinecolor=P["grid"], linecolor=P["grid"], tickfont=dict(color=P["muted"]))
    return fig
