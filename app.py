import json
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from pathlib import Path

st.set_page_config(page_title="GeoVisualizador Futrono", layout="wide")
st.title("GeoVisualizador de Futrono")
st.write("Aplicación para visualizar capas geoespaciales de la comuna de Futrono, Región de Los Ríos, Chile. Datos proyectados en EPSG:32718 (UTM 18S).")

DATA = Path("data")

# ── Estilos por capa ──────────────────────────────────────────

ESTILO_LIMITE = {
    "color": "#8B0000", "weight": 3, "fillColor": "#000000",
    "fillOpacity": 0.05, "opacity": 0.9,
}

ESTILO_LAGOS = {
    "color": "#0D47A1", "weight": 1.5, "fillColor": "#1565C0",
    "fillOpacity": 0.45, "opacity": 0.8,
}

ESTILO_PAC = {
    "color": "#CC0000", "weight": 1, "fillColor": "#FF4444",
    "fillOpacity": 0.7, "opacity": 0.8,
}

ESTILO_RED_HIDRO = {
    "color": "#1565C0", "weight": 2.5, "opacity": 0.85,
}

ESTILO_RED_VIAL = {
    "color": "#E05000", "weight": 2, "opacity": 0.8,
}

ESTILO_TOPONIMIA = {
    "color": "#333333", "weight": 1, "fillColor": "#FFD700",
    "fillOpacity": 0.6,
}

# ── Cargar archivos ───────────────────────────────────────────

ARCHIVOS = {
    "Límite Comunal": "limite_comunal_futrono_18s.shp",
    "Área Construida 2015-2016": "shape_superficie_area_construida_2015-2016.shp",
    "Área Construida 2024-2025": "shape_area_construida_2024-2025.shp",
    "Red Hidrográfica": "red_hidrográfica_futrono_18s.shp",
    "Red Vial": "red_vial_futrono4.shp",
    "Toponimia": "toponimia_futrono.shp",
    "Lagos": "lagos_futrono.shp",
}

def limpiar_gdf(gdf):
    """Limpia columnas no serializables del GeoDataFrame."""
    gdf = gdf.copy()
    for col in gdf.columns:
        if col == gdf.geometry.name:
            continue
        if "datetime" in str(gdf[col].dtype) or "timedelta" in str(gdf[col].dtype):
            gdf[col] = gdf[col].astype(str)
    return gdf

capas = {}
for nombre, archivo in ARCHIVOS.items():
    ruta = DATA / archivo
    if ruta.exists():
        try:
            gdf = gpd.read_file(ruta)
            if len(gdf) == 0:
                st.warning(f"{archivo} está vacío")
                continue
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:32718")
            if gdf.crs is not None and gdf.crs.to_epsg() not in (4326, None):
                gdf = gdf.to_crs(4326)
            gdf = limpiar_gdf(gdf)
            capas[nombre] = gdf
        except Exception as e:
            st.warning(f"Error al cargar {archivo}: {e}")
    else:
        st.warning(f"Archivo no encontrado: {archivo}")

# ── Sidebar ───────────────────────────────────────────────────

st.sidebar.title("Capas disponibles")
capas_activas = []
for nombre in ARCHIVOS:
    if nombre in capas:
        if st.sidebar.checkbox(nombre, value=True, key=nombre):
            capas_activas.append(nombre)
    else:
        st.sidebar.checkbox(nombre, value=False, disabled=True, key=f"disabled_{nombre}")

# ── Mapa base ─────────────────────────────────────────────────

centro = [-40.05, -72.87]
if "Límite Comunal" in capas:
    c = capas["Límite Comunal"].unary_union.centroid
    centro = [c.y, c.x]

m = folium.Map(location=centro, zoom_start=13, tiles="OpenStreetMap")
folium.TileLayer("CartoDB positron", name="Mapa claro").add_to(m)
folium.TileLayer("CartoDB dark_matter", name="Mapa oscuro").add_to(m)

# ── Renderizar capas ──────────────────────────────────────────

for nombre in capas_activas:
    gdf = capas[nombre]
    cols = [c for c in gdf.columns if c != gdf.geometry.name][:3]

    if "Límite" in nombre:
        folium.GeoJson(
            gdf, name=nombre,
            style_function=lambda f, e=ESTILO_LIMITE: dict(e),
            tooltip=folium.GeoJsonTooltip(fields=cols) if cols else None,
        ).add_to(m)

    elif "Lagos" in nombre:
        folium.GeoJson(
            gdf, name=nombre,
            style_function=lambda f, e=ESTILO_LAGOS: dict(e),
            tooltip=folium.GeoJsonTooltip(fields=cols) if cols else None,
        ).add_to(m)

    elif "2024-2025" in nombre:
        st.write(f"🟠 {nombre}: {len(gdf)} geometrías")
        folium.GeoJson(
            gdf, name=nombre,
            style_function=lambda f: {
                "color": "#FF8800", "weight": 2,
                "fillColor": "#FFAA00", "fillOpacity": 0.6,
            },
            tooltip=folium.GeoJsonTooltip(fields=cols) if cols else None,
        ).add_to(m)

    elif "Área Construida" in nombre:
        st.write(f"🔴 {nombre}: {len(gdf)} geometrías")
        folium.GeoJson(
            gdf, name=nombre,
            style_function=lambda f: {
                "color": "#CC0000", "weight": 2,
                "fillColor": "#FF4444", "fillOpacity": 0.6,
            },
            tooltip=folium.GeoJsonTooltip(fields=cols) if cols else None,
        ).add_to(m)

    elif "Hidrográfica" in nombre:
        folium.GeoJson(
            gdf, name=nombre,
            style_function=lambda f, e=ESTILO_RED_HIDRO: dict(e),
            tooltip=folium.GeoJsonTooltip(fields=cols) if cols else None,
        ).add_to(m)

    elif "Vial" in nombre:
        folium.GeoJson(
            gdf, name=nombre,
            style_function=lambda f, e=ESTILO_RED_VIAL: dict(e),
            tooltip=folium.GeoJsonTooltip(fields=cols) if cols else None,
        ).add_to(m)

    elif "Toponimia" in nombre:
        for _, row in gdf.iterrows():
            punto = row.geometry
            if punto is not None:
                lat, lon = punto.y, punto.x
                nombre_lugar = row.get("nombre", row.get("NOMBRE", ""))
                folium.Marker(
                    [lat, lon],
                    popup=nombre_lugar,
                    tooltip=nombre_lugar,
                    icon=folium.Icon(color="green", icon="info-sign"),
                ).add_to(m)

folium.LayerControl(collapsed=True).add_to(m)

# CSS inline para que el control de capas no se corte
st.markdown("""
<style>
  .folium-map .leaflet-control-layers {
    max-width: 220px !important;
  }
  .folium-map .leaflet-control-layers-list {
    font-size: 11px !important;
  }
</style>
""", unsafe_allow_html=True)

st_folium(m, width=1200, height=700)

st.sidebar.markdown("---")
st.sidebar.write(f"Capas cargadas: **{len(capas)}**")
st.sidebar.write(f"Capas activas:  **{len(capas_activas)}**")
