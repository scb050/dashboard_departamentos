# app.py — Mapa interactivo (PyDeck) SIN pandas/folium

import csv
import json
from pathlib import Path
import streamlit as st
import pydeck as pdk
from math import isnan

st.set_page_config(page_title="Mapa por Departamentos", layout="wide")
st.title("Dashboard Geográfico — Departamentos")

BASE = Path(__file__).parent
DATA = BASE / "data"
GEOJSON_PATH = DATA / "departamentos.geojson"
CSV_PATH = DATA / "atributos.csv"

# -------- utilidades --------
def read_csv_dicts(path: Path):
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows

def to_float_or_none(x):
    try:
        v = float(str(x).replace(",", "."))
        #  evitar inf/nan
        if v != v:  # NaN
            return None
        return v
    except Exception:
        return None

def quantiles(values, k=5):
    """k clases (k=5 → 6 cortes). Sin numpy."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return [0, 1]
    qs = []
    for i in range(k+1):
        pos = i * (len(vals)-1) / k
        lo, hi = int(pos), min(int(pos)+1, len(vals)-1)
        w = pos - lo
        qs.append(vals[lo] * (1-w) + vals[hi] * w)
    return qs

def approximate_center(geojson):
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")

    def it(geom):
        if not geom: return
        t = geom.get("type")
        if t == "Polygon":
            for ring in geom["coordinates"]:
                for x, y in ring: yield x, y
        elif t == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    for x, y in ring: yield x, y

    for feat in geojson.get("features", []):
        for x, y in it(feat.get("geometry")):
            xmin = min(xmin, x); ymin = min(ymin, y)
            xmax = max(xmax, x); ymax = max(ymax, y)

    if xmin == float("inf"):
        return 4.6, -74.3, 4.5
    lat = (ymin + ymax) / 2.0
    lon = (xmin + xmax) / 2.0
    span = max(xmax - xmin, ymax - ymin)
    zoom = 4.5 if span > 15 else 5.0
    return lat, lon, zoom

# -------- carga de datos --------
with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
    gj = json.load(f)

rows = read_csv_dicts(CSV_PATH)

# claves/columnas
GEO_KEY = "DPTO_CCDGO"
csv_cols = list(rows[0].keys()) if rows else []
DF_KEY = GEO_KEY if GEO_KEY in csv_cols else (csv_cols[0] if csv_cols else GEO_KEY)

# detectar columnas numéricas
num_cols = []
for c in csv_cols:
    if c == DF_KEY: 
        continue
    any_float = any(to_float_or_none(r.get(c)) is not None for r in rows[:50])
    if any_float:
        num_cols.append(c)
if not num_cols:
    num_cols = [c for c in csv_cols if c != DF_KEY] or [DF_KEY]

default_idx = num_cols.index("DIRECTORIO") if "DIRECTORIO" in num_cols else 0

st.sidebar.header("Configuración del mapa")
metric = st.sidebar.selectbox("Variable numérica para coropletas", num_cols, index=default_idx)

# mapa de valores por código
values_map = {}
for r in rows:
    key = str(r.get(DF_KEY, "")).strip()
    val = to_float_or_none(r.get(metric))
    if key:
        values_map[key] = val

# paleta
palette = [
    [239, 243, 255],
    [189, 215, 231],
    [107, 174, 214],
    [49, 130, 189],
    [8, 81, 156],
]
qs = quantiles([v for v in values_map.values() if v is not None], k=5)
if len(qs) < 2:
    qs = [0, 1]

def color_for_value(v):
    if v is None:
        return [230, 230, 230, 160]
    for i in range(5):
        if qs[i] <= v <= qs[i+1]:
            return palette[i] + [180]
    return palette[-1] + [180]

# inyectar propiedades para tooltip/color
for feat in gj.get("features", []):
    props = feat.setdefault("properties", {})
    key = str(props.get(GEO_KEY, "")).strip()
    val = values_map.get(key)
    props["_value"] = val if val is not None else None
    props["_color"] = color_for_value(val)
    props["_label"] = f"{GEO_KEY}: {key}<br>{metric}: {val if val is not None else 'N/A'}"

lat, lon, zoom = approximate_center(gj)

layer = pdk.Layer(
    "GeoJsonLayer",
    data=gj,
    stroked=True,
    filled=True,
    get_fill_color="properties._color",
    get_line_color=[80,80,80],
    get_line_width=1,
    pickable=True,
    auto_highlight=True,
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom),
    tooltip={"html": "{properties._label}", "style": {"backgroundColor": "rgba(50,50,50,0.85)", "color":"white"}},
    map_provider=None,   # sin token
)

st.pydeck_chart(deck, use_container_width=True)

# leyenda simple
if len(qs) >= 2:
    st.markdown(
        "**Clases (cuantiles):** " + 
        ", ".join([f"{qs[i]:.0f}–{qs[i+1]:.0f}" for i in range(len(qs)-1)])
        + f" &nbsp;&nbsp;|&nbsp;&nbsp; **Variable:** `{metric}`"
    )

