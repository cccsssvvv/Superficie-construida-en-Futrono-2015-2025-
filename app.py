import json
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from pathlib import Path

import matplotlib.pyplot as plt
import analisis_crecimiento as ac

st.set_page_config(page_title="GeoVisualizador Futrono", layout="wide")
st.title("GeoVisualizador de Futrono")
st.write("Aplicación para visualizar capas geoespaciales de la comuna de Futrono, Región de Los Ríos, Chile. Datos proyectados en EPSG:32718 (UTM 18S).")

DATA = Path("data")

# ── Estilos por capa ──────────────────────────────────────────

ESTILO_LIMITE = {
    "color": "#8B0000", "weight": 3, "fillColor": "#000000",
    "fillOpacity": 0.05, "opacity": 0.9,
}

ESTILO_RED_HIDRO = {
    "color": "#1565C0", "weight": 2.5, "opacity": 0.85,
}

ESTILO_RED_VIAL = {
    "color": "#E05000", "weight": 2, "opacity": 0.8,
}

# ── Cargar archivos ───────────────────────────────────────────

ARCHIVOS = {
    "Límite Comunal": "limite_comunal_futrono_18s.shp",
    "Área Construida 2015-2016": "area_construida_futrono_2015-2016.geojson",
    "Área Construida 2024-2025": "area_construida_futrono_2024-2025.geojson",
    "Red Hidrográfica": "red_hidrográfica_futrono_18s.shp",
    "Red Vial": "red_vial_futrono4.shp",
    "Localidades": "tasa_crecimiento_localidades_futrono.geojson",
}

def limpiar_gdf(gdf):
    """Convierte todas las columnas (excepto geometría) a tipos serializables JSON."""
    gdf = gdf.copy()
    for col in gdf.columns:
        if col == gdf.geometry.name:
            continue
        dtype = str(gdf[col].dtype)
        if "datetime" in dtype or "timedelta" in dtype:
            gdf[col] = gdf[col].astype(str)
        elif "int" in dtype:
            gdf[col] = gdf[col].astype(int)
        elif "float" in dtype:
            gdf[col] = gdf[col].astype(float)
        else:
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

def serializar_gdf(gdf):
    """Convierte GeoDataFrame a dict JSON-serializable para folium."""
    return json.loads(gdf.to_json())

def tooltip_fields(gdf):
    """Retorna campos no-geométricos para tooltip."""
    return [c for c in gdf.columns if c != gdf.geometry.name][:5]

for nombre in capas_activas:
    gdf = capas[nombre]
    data_json = serializar_gdf(gdf)
    campos = tooltip_fields(gdf)

    if "Límite" in nombre:
        folium.GeoJson(
            data_json, name=nombre,
            style_function=lambda f, e=ESTILO_LIMITE: dict(e),
            tooltip=folium.GeoJsonTooltip(fields=campos) if campos else None,
        ).add_to(m)

    elif "2024-2025" in nombre:
        st.write(f"🟠 {nombre}: {len(gdf)} geometrías")
        folium.GeoJson(
            data_json, name=nombre,
            style_function=lambda f: {
                "color": "#FF8800", "weight": 2,
                "fillColor": "#FFAA00", "fillOpacity": 0.6,
            },
            tooltip=folium.GeoJsonTooltip(fields=campos) if campos else None,
        ).add_to(m)

    elif "Área Construida" in nombre:
        st.write(f"🔴 {nombre}: {len(gdf)} geometrías")
        folium.GeoJson(
            data_json, name=nombre,
            style_function=lambda f: {
                "color": "#CC0000", "weight": 2,
                "fillColor": "#FF4444", "fillOpacity": 0.6,
            },
            tooltip=folium.GeoJsonTooltip(fields=campos) if campos else None,
        ).add_to(m)

    elif "Hidrográfica" in nombre:
        folium.GeoJson(
            data_json, name=nombre,
            style_function=lambda f, e=ESTILO_RED_HIDRO: dict(e),
            tooltip=folium.GeoJsonTooltip(fields=campos) if campos else None,
        ).add_to(m)

    elif "Vial" in nombre:
        folium.GeoJson(
            data_json, name=nombre,
            style_function=lambda f, e=ESTILO_RED_VIAL: dict(e),
            tooltip=folium.GeoJsonTooltip(fields=campos) if campos else None,
        ).add_to(m)

    elif "Localidades" in nombre:
        folium.GeoJson(
            data_json, name=nombre,
            style_function=lambda f: {
                "color": "#333333",
                "weight": 2,
                "fillColor": ac.estilo_qml_para_folium(f["properties"].get("diferencia_relativa", 0)),
                "fillOpacity": 0.7,
            },
            tooltip=folium.GeoJsonTooltip(fields=campos) if campos else None,
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

# ── Análisis de crecimiento ─────────────────────────────────────

if "Localidades" not in capas:
    st.warning("Capa de localidades no disponible para análisis de crecimiento")
else:
    st.markdown("---")
    st.header("Análisis de crecimiento de área construida")

    if st.button("Ejecutar análisis de crecimiento", type="primary"):
        with st.spinner("Procesando datos espaciales..."):
            try:
                a_2016, a_2025, loc = ac.cargar_datos()
                df = ac.procesar_datos(a_2016, a_2025, loc)
                df = ac.clasificar(df)
                df["LOCALIDAD"] = df["LOCALIDAD"].astype(str).str.strip()
                df = df.sort_values("diferencia_relativa", ascending=False)
                st.session_state["df_crecimiento"] = df
                st.success(f"Análisis completado: {len(df)} localidades procesadas")
            except Exception as e:
                st.error(f"Error en el análisis: {e}")

    if "df_crecimiento" in st.session_state:
        df = st.session_state["df_crecimiento"]

        with st.expander("Ver tabla de datos", expanded=False):
            mostrar = df[["LOCALIDAD", "area_total_2016", "area_total_2025",
                          "diferencia_relativa", "clasificacion"]].copy()
            mostrar.columns = ["Localidad", "Área 2015-16 (m²)", "Área 2024-25 (m²)",
                               "Diferencia relativa (%)", "Clasificación"]
            st.dataframe(mostrar, use_container_width=True)

            csv = mostrar.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("Descargar CSV", csv, "crecimiento_localidades.csv", "text/csv")

        tab1, tab2, tab3, tab4 = st.tabs([
            "Crecimiento por localidad", "Distribución", "Histograma", "Área comparativa",
        ])

        with tab1:
            fig, ax = plt.subplots(figsize=(10, 6))
            ac.grafico_barras_crecimiento(df, ax)
            plt.tight_layout()
            st.pyplot(fig)

        with tab2:
            fig, ax = plt.subplots(figsize=(6, 6))
            ac.grafico_pie_clasificacion(df, ax)
            plt.tight_layout()
            st.pyplot(fig)

        with tab3:
            fig, ax = plt.subplots(figsize=(8, 4))
            ac.grafico_histograma(df, ax)
            plt.tight_layout()
            st.pyplot(fig)

        with tab4:
            fig, ax = plt.subplots(figsize=(10, 6))
            ac.grafico_area_comparativa(df, ax, max_items=15)
            plt.tight_layout()
            st.pyplot(fig)

        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        total = len(df)
        for col, clase in zip(
            [col1, col2, col3],
            ["Decrecimiento alto", "Decrecimiento moderado", "Sin crecimiento"],
        ):
            n = len(df[df["clasificacion"] == clase])
            col.metric(clase, f"{n}", f"{n/total*100:.1f}%" if total else "")
        for col, clase in zip(
            [col1, col2, col3],
            ["Crecimiento moderado", "Crecimiento alto"],
        ):
            n = len(df[df["clasificacion"] == clase])
            col.metric(clase, f"{n}", f"{n/total*100:.1f}%" if total else "")

st.sidebar.markdown("---")
st.sidebar.write(f"Capas cargadas: **{len(capas)}**")
st.sidebar.write(f"Capas activas:  **{len(capas_activas)}**")
