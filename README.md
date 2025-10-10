# Dashboard Geográfico — Departamentos (Streamlit + Folium)

Este repositorio contiene un dashboard en **Streamlit** que visualiza un GeoJSON de departamentos y permite generar un mapa coroplético por una variable numérica.

## Estructura
```
.
├── app.py
├── requirements.txt
├── render.yaml
└── data/
    ├── departamentos.geojson
    └── atributos.csv
```

## Ejecutar localmente
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Despliegue en Render
1. Sube este repo a GitHub.
2. Entra a https://dashboard.render.com/ → **New +** → **Web Service** → **Build and deploy from a Git repository**.
3. Selecciona el repositorio. En **Environment** elige *Python*.
4. **Build Command:** `pip install -r requirements.txt`  
   **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
5. Crea el servicio. Render instalará dependencias y levantará la app.

> Nota: Para simplificar el despliegue no usamos GeoPandas (evita GDAL). El GeoJSON ya está incluido en `data/`.
