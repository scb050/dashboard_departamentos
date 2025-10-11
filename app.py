import json
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium

# --- NUEVO: para modo estático ---
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
from matplotlib.colors import Normalize
import numpy as np

st.set_page_config(page_title="Mapa por Departamentos", layout="wide")
st.title("Dashboard Geográfico — Departamentos")

# Rutas de datos
data_dir = Path(__file__).parent / "data"
geojson_file = data_dir / "departamentos.geojson"
attr_csv = data_dir / "atributos.csv"

@st.cache_data
def load_data():
    with open(geojson_file, "r", encoding="utf-8") as f:
        gj = json.load(f)
    df = pd.read_csv(attr_csv)
    return gj, df

gj, df = load_data()

# Fijamos claves conocidas (evita heurísticas)
geo_key = "DPTO_CCDGO"
df_key = "DPTO_CCDGO" if "DPTO_CCDGO" in df.columns else df.columns[0]

# Sidebar
st.sidebar.header("Configuración del mapa")

# Numéricas reales (excluye clave)
numeric_cols = [c for c in df.select_dtypes(include="number").columns if c != df_key]
if not numeric_cols:
    df["valor_demo"] = range(len(df))
    numeric_cols = ["valor_demo"]

metric = st.sidebar.selectbox("Variable numérica para coropletas", numeric_cols, index=0)
tiles = st.sidebar.selectbox("Base cartográfica", ["OpenStreetMap", "CartoDB positron", "Stamen Terrain", "Stamen Toner"])
show_labels = st.sidebar.checkbox("Mostrar etiquetas emergentes (popup)", value=True)

# --- NUEVO: selector de modo ---
mode = st.sidebar.radio("Modo de render", ["Interactivo (Folium)", "Estático (PNG)"], index=0)

# Helpers
def approximate_center(feature_collection):
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")

    def coord_iter(geom):
        if geom is None:
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

    for feat in feature_collection["features"]:
        geom = feat.get("geometry")
        if geom:
            for x, y in coord_iter(geom):
                xmin = min(xmin, x); ymin = min(ymin, y)
                xmax = max(xmax, x); ymax = max(ymax, y)

    if xmin == float("inf"):
        return 4.5709, -74.2973, (-79, -66, -4.5, 13.5)  # centro Colombia + bounds aprox
    return (ymin + ymax) / 2.0, (xmin + xmax) / 2.0, (xmin, xmax, ymin, ymax)

center_lat, center_lon, bounds = approximate_center(gj)

# Preparar join
df2 = df.copy()
df2[df_key] = df2[df_key].astype(str)
df2[metric] = pd.to_numeric(df2[metric], errors="coerce")
df2 = df2[[df_key, metric]].dropna(subset=[metric])

value_map = {str(k): float(v) for k, v in zip(df2[df_key], df2[metric])}

# ================ MODO INTERACTIVO (FOLIUM) ================
if mode == "Interactivo (Folium)":
    m = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles=tiles)

    # Choropleth (usamos el dict cargado para evitar issues de encoding)
    if not df2.empty:
        join_df = df2.rename(columns={df_key: "key", metric: "value"})
        folium.Choropleth(
            geo_data=gj,
            data=join_df,
            columns=["key", "value"],
            key_on=f"feature.properties.{geo_key}",
            fill_opacity=0.7,
            line_opacity=0.4,
            legend_name=metric,
            nan_fill_opacity=0.1,
            highlight=True
        ).add_to(m)

    # Bordes + tooltips
    gj_layer = folium.GeoJson(
        data=gj,
        name="Departamentos",
        style_function=lambda feature: {"fillOpacity": 0.0, "weight": 1, "color": "#555555"},
        tooltip=folium.GeoJsonTooltip(fields=[geo_key], aliases=[geo_key])
    )
    if show_labels:
        gj_layer.add_child(folium.features.GeoJsonPopup(fields=[geo_key, metric] if metric in df.columns else [geo_key]))
    gj_layer.add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, height=650, use_container_width=True)

# ================ MODO ESTÁTICO (PNG) ================
else:
    # Preparar patches de polígonos sin shapely
    patches = []
    colors = []

    vmin = np.nanmin(list(value_map.values())) if value_map else 0.0
    vmax = np.nanmax(list(value_map.values())) if value_map else 1.0
    if vmin == vmax:
        vmax = vmin + 1.0
    norm = Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.Blues  # paleta base

    def add_polygon(coords, val):
        # coords: lista [(x,y),...]
        if len(coords) >= 3:
            patches.append(MplPolygon(coords, closed=True, linewidth=0.5))
            colors.append(cmap(norm(val)) if val is not None else (0.9, 0.9, 0.9, 1.0))

    for feat in gj["features"]:
        geom = feat.get("geometry")
        props = feat.get("properties", {})
        key_val = str(props.get(geo_key))
        val = value_map.get(key_val, None)

        if not geom:
            continue

        t = geom.get("type")
        if t == "Polygon":
            for ring in geom["coordinates"]:
                add_polygon([(x, y) for x, y in ring], val)
        elif t == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    add_polygon([(x, y) for x, y in ring], val)

    fig, ax = plt.subplots(figsize=(8, 9))
    if patches:
        pc = PatchCollection(patches, facecolor=colors, edgecolor="#555555", linewidths=0.5)
        ax.add_collection(pc)

    # Límites del mapa
    xmin, xmax, ymin, ymax = bounds
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.030, pad=0.02)
    cbar.set_label(metric)

    st.pyplot(fig, clear_figure=True)






