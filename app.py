import json
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="Mapa por Departamentos", layout="wide")
st.title("Dashboard Geográfico — Departamentos")

data_dir = Path(__file__).parent / "data"
geojson_file = data_dir / "departamentos.geojson"
attr_csv = data_dir / "atributos.csv"

# --------- Carga de datos ----------
with open(geojson_file, "r", encoding="utf-8") as f:
    gj = json.load(f)

df = pd.read_csv(attr_csv)

# ----- Heurística de clave para unir -----
first_props = gj["features"][0]["properties"]
props_cols = list(first_props.keys())

preferred_keys = [
    "COD_DANE", "cod_dane", "COD_DPT", "COD_DPTO", "COD_DTO",
    "DPTO", "Dpto", "DEPARTAMENTO", "Departamento",
    "NOMBRE", "Nombre", "ID", "id", "codigo", "Codigo"
]
geo_key = next((k for k in preferred_keys if k in props_cols), props_cols[0])

df_cols = df.columns.tolist()
df_key = next((c for c in df_cols if c.lower() == geo_key.lower()), df_cols[0])

# --------- Sidebar ----------
st.sidebar.header("Configuración del mapa")

# Numéricas reales, EXCLUYENDO la clave
numeric_cols_all = df.select_dtypes(include="number").columns.tolist()
numeric_cols = [c for c in numeric_cols_all if c != df_key]

# Si no hay numéricas (o todas eran la clave), creamos demo
if len(numeric_cols) == 0:
    df["valor_demo"] = range(len(df))
    numeric_cols = ["valor_demo"]

metric = st.sidebar.selectbox("Variable numérica para coropletas", numeric_cols)
tiles = st.sidebar.selectbox(
    "Base cartográfica",
    ["OpenStreetMap", "CartoDB positron", "Stamen Terrain", "Stamen Toner"]
)
show_labels = st.sidebar.checkbox("Mostrar etiquetas emergentes (popup)", value=True)

# --------- Centro aproximado del mapa ----------
def approximate_center(feature_collection):
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")

    def coord_iter(geom):
        if geom is None:
            return
        if geom["type"] == "Polygon":
            for ring in geom["coordinates"]:
                for x, y in ring:
                    yield x, y
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                for ring in poly:
                    for x, y in ring:
                        yield x, y

    for feat in feature_collection["features"]:
        for x, y in coord_iter(feat.get("geometry")):
            xmin = min(xmin, x); ymin = min(ymin, y)
            xmax = max(xmax, x); ymax = max(ymax, y)

    if xmin == float("inf"):
        return 4.5709, -74.2973  # Colombia
    return (ymin + ymax) / 2.0, (xmin + xmax) / 2.0

center_lat, center_lon = approximate_center(gj)
m = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles=tiles)

# --------- Preparar datos para choropleth ----------
df2 = df.copy()
df2[df_key] = df2[df_key].astype(str)

# Si metric == df_key, duplica a temporal para evitar choque al renombrar
metric_col = metric
if metric == df_key:
    metric_col = "__metric__dup__"
    df2[metric_col] = pd.to_numeric(df2[metric], errors="coerce")
else:
    df2[metric_col] = pd.to_numeric(df2[metric], errors="coerce")

df2 = df2[[df_key, metric_col]].dropna(subset=[metric_col])

if df2.empty:
    st.warning("La columna seleccionada no tiene valores numéricos válidos para colorear. Se mostrará solo el contorno.")
else:
    join_df = df2.rename(columns={df_key: "key", metric_col: "value"}).copy()
    join_df["key"] = join_df["key"].astype(str)
    join_df["value"] = pd.to_numeric(join_df["value"], errors="coerce")
    join_df = join_df.dropna(subset=["value"])

    if not join_df.empty:
        folium.Choropleth(
            geo_data=gj,                      # usar dict -> evita problemas de encoding
            data=join_df,
            columns=["key", "value"],
            key_on=f"feature.properties.{geo_key}",
            fill_opacity=0.7,
            line_opacity=0.4,
            legend_name=metric,
            nan_fill_opacity=0.1,
            highlight=True
        ).add_to(m)
    else:
        st.warning("No quedaron filas válidas después de limpiar la métrica seleccionada.")

# --------- Capa de polígonos + tooltip/popup ----------
tooltip_fields = [geo_key] + [c for c in df.columns if c != df_key]
tooltip_fields = tooltip_fields[:6]

def style_function(feature):
    return {"fillOpacity": 0.0, "weight": 1, "color": "#555555"}

gj_layer = folium.GeoJson(
    data=gj,                                # usar dict -> evita problemas de encoding
    name="Departamentos",
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(fields=[geo_key], aliases=[geo_key])
)
if show_labels:
    gj_layer.add_child(folium.features.GeoJsonPopup(fields=tooltip_fields))
gj_layer.add_to(m)

folium.LayerControl().add_to(m)

# Render en Streamlit
st_folium(m, height=650)





