# app.py — Mapa interactivo simple con PyDeck (sin Folium)

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk

st.set_page_config(page_title="Mapa por Departamentos", layout="wide")
st.title("Dashboard Geográfico — Departamentos")

# Rutas
BASE = Path(__file__).parent
DATA = BASE / "data"
GEOJSON_PATH = DATA / "departamentos.geojson"
CSV_PATH = DATA / "atributos.csv"

@st.cache_data
def load_data():
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        gj = json.load(f)
    df = pd.read_csv(CSV_PATH)
    return gj, df

gj, df = load_data()

# Fijar claves
GEO_KEY = "DPTO_CCDGO"
DF_KEY = "DPTO_CCDGO" if "DPTO_CCDGO" in df.columns else df.columns[0]

# --- Sidebar ---
st.sidebar.header("Configuración del mapa")

# Columnas numéricas (excluye la clave)
numeric_cols = [c for c in df.select_dtypes(include="number").columns if c != DF_KEY]
if not numeric_cols:
    df["valor_demo"] = range(len(df))
    numeric_cols = ["valor_demo"]

# Si existe DIRECTORIO, úsala por defecto
default_idx = numeric_cols.index("DIRECTORIO") if "DIRECTORIO" in numeric_cols else 0
metric = st.sidebar.selectbox("Variable numérica para coropletas", numeric_cols, index=default_idx)

# --- Join: df -> geojson properties ---
df2 = df[[DF_KEY, metric]].copy()
df2[DF_KEY] = df2[DF_KEY].astype(str)
df2[metric] = pd.to_numeric(df2[metric], errors="coerce")
df2 = df2.dropna(subset=[metric])

values_map = dict(zip(df2[DF_KEY], df2[metric]))

# paleta de 5 clases (azules)
palette = [
    [239, 243, 255],
    [189, 215, 231],
    [107, 174, 214],
    [49, 130, 189],
    [8, 81, 156],
]

vals = np.array(list(values_map.values())) if values_map else np.array([0, 1])
q = np.quantile(vals, [0, 0.2, 0.4, 0.6, 0.8, 1.0]).tolist()

def color_for_value(v: float):
    if v is None or not np.isfinite(v):
        return [230, 230, 230, 160]
    # asignar clase según cuantiles
    for i in range(5):
        if q[i] <= v <= q[i+1]:
            return palette[i] + [180]  # RGBA
    return palette[-1] + [180]

# Meter valor y color dentro de cada feature
for feat in gj.get("features", []):
    props = feat.setdefault("properties", {})
    key = str(props.get(GEO_KEY, ""))
    val = values_map.get(key, None)
    props["_value"] = None if val is None else float(val)
    props["_color"] = color_for_value(val)
    # tooltip seguro
    props["_label"] = f"{GEO_KEY}: {key}<br>{metric}: {props['_value'] if props['_value'] is not None else 'N/A'}"

# Calcular centro aproximado para la vista
def approximate_center(feature_collection):
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")

    def iter_coords(geom):
        if not geom: 
            return
        t = geom.get("type")
        if t == "Polygon":
            for ring in geom["coordinates"]:
                for x, y in ring:
                    yield x, y
        elif t == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    for x, y in ring:
                        yield x, y

    for f in feature_collection.get("features", []):
        for x, y in iter_coords(f.get("geometry")):
            xmin = min(xmin, x); ymin = min(ymin, y)
            xmax = max(xmax, x); ymax = max(ymax, y)

    if xmin == float("inf"):
        # Colombia aprox
        return 4.6, -74.3, 4.5
    lat = (ymin + ymax) / 2.0
    lon = (xmin + xmax) / 2.0
    # zoom heurístico
    span = max(xmax - xmin, ymax - ymin)
    zoom = 4.5 if span > 15 else 5.0
    return lat, lon, zoom

lat, lon, zoom = approximate_center(gj)

# Capa GeoJSON
layer = pdk.Layer(
    "GeoJsonLayer",
    data=gj,  # dict, no ruta
    stroked=True,
    filled=True,
    get_fill_color="properties._color",
    get_line_color=[80, 80, 80],
    get_line_width=1,
    pickable=True,
    auto_highlight=True,
)

# Tooltip
tooltip = {
    "html": "{properties._label}",
    "style": {"backgroundColor": "rgba(50, 50, 50, 0.8)", "color": "white"}
}

# Vista y render
view = pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom)
deck = pdk.Deck(layers=[layer], initial_view_state=view, tooltip=tooltip, map_provider=None)  # sin basemap (evita token)
st.pydeck_chart(deck, use_container_width=True)

# Leyenda mínima
st.markdown(f"**Variable:** `{metric}` &nbsp;&nbsp; | &nbsp;&nbsp; Clases por cuantiles: {', '.join([f'{q[i]:.0f}-{q[i+1]:.0f}' for i in range(5)])}")







