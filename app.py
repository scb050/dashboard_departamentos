# app.py — Mapa interactivo PyDeck sin pandas/folium

import csv
import json
from pathlib import Path
import streamlit as st
import pydeck as pdk

st.set_page_config(page_title="Mapa por Departamentos", layout="wide")
st.title("Dashboard Geográfico — Departamentos")

# ------------------- Rutas -------------------
BASE = Path(__file__).parent
DATA = BASE / "data"
GEOJSON_PATH = DATA / "departamentos.geojson"
CSV_PATH = DATA / "atributos.csv"

# ------------------- Utilidades -------------------
def read_csv_dicts(path: Path):
    """Lee CSV como lista de diccionarios (sin pandas)."""
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            # limpiamos espacios por si acaso
            rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items()})
    return rows

def to_float_or_none(x):
    """Convierte a float; si no puede, devuelve None."""
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def quantiles(values, k=5):
    """Cuantiles sin numpy (k clases => k+1 cortes)."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return [0, 1]
    qs = []
    for i in range(k + 1):
        pos = i * (len(vals) - 1) / k
        lo, hi = int(pos), min(int(pos) + 1, len(vals) - 1)
        w = pos - lo
        qs.append(vals[lo] * (1 - w) + vals[hi] * w)
    return qs

# ------------------- Carga de datos -------------------
with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
    gj = json.load(f)

rows = read_csv_dicts(CSV_PATH)

# claves
GEO_KEY = "DPTO_CCDGO"
csv_cols = list(rows[0].keys()) if rows else []
DF_KEY = GEO_KEY if GEO_KEY in csv_cols else (csv_cols[0] if csv_cols else GEO_KEY)

# columnas numéricas (heurística simple)
num_cols = []
for c in csv_cols:
    if c == DF_KEY:
        continue
    if any(to_float_or_none(r.get(c)) is not None for r in rows[:50]):
        num_cols.append(c)
if not num_cols:
    # si no detecta ninguna, usa cualquiera distinta de la clave
    num_cols = [c for c in csv_cols if c != DF_KEY] or [DF_KEY]

default_idx = num_cols.index("DIRECTORIO") if "DIRECTORIO" in num_cols else 0

# ------------------- UI -------------------
st.sidebar.header("Configuración del mapa")
metric = st.sidebar.selectbox("Variable numérica para coropletas", num_cols, index=default_idx)

# valores por código
values_map = {}
for r in rows:
    key = str(r.get(DF_KEY, "")).strip()
    val = to_float_or_none(r.get(metric))
    if key:
        values_map[key] = val

# paleta y cortes (5 clases por cuantiles)
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
        return [230, 230, 230, 180]  # gris para NA
    for i in range(5):
        if qs[i] <= v <= qs[i + 1]:
            return palette[i] + [200]
    return palette[-1] + [200]

# inyectamos color y tooltip en cada feature
for feat in gj.get("features", []):
    props = feat.setdefault("properties", {})
    key = str(props.get(GEO_KEY, "")).strip()
    val = values_map.get(key)
    props["_value"] = val if val is not None else None
    props["_color"] = color_for_value(val)
    props["_label"] = f"{GEO_KEY}: {key}<br>{metric}: {val if val is not None else 'N/A'}"

# ------------------- Vista fija sobre Colombia -------------------
lat, lon, zoom = 4.6, -74.3, 4.5  # centro y zoom aprox de Colombia

# capa GeoJSON
layer = pdk.Layer(
    "GeoJsonLayer",
    data=gj,                     # pasamos el dict, no una URL
    stroked=True,
    filled=True,
    get_fill_color="properties._color",
    get_line_color=[80, 80, 80],
    get_line_width=1,
    pickable=True,
    auto_highlight=True,
)

# Mapa sin Mapbox (evita token y pantallas en blanco)
view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom)
view = pdk.View(type="MapView", controller=True)
deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    views=[view],
    tooltip={
        "html": "{properties._label}",
        "style": {"backgroundColor": "rgba(50,50,50,0.85)", "color": "white"},
    },
    map_style=None,  # sin basemap de Mapbox
)

# IMPORTANTE: no usar 'height=' en esta versión de Streamlit
st.pydeck_chart(deck, use_container_width=True)

# Leyenda
if len(qs) >= 2:
    st.markdown(
        "__Clases (cuantiles)__: "
        + ", ".join([f"{qs[i]:.0f}–{qs[i+1]:.0f}" for i in range(len(qs) - 1)])
        + f" &nbsp;&nbsp;|&nbsp;&nbsp; **Variable:** `{metric}`"
    )



