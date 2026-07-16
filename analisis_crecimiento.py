import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import io
from pathlib import Path

matplotlib.use('Agg')

RUTAS = {
    "construida_2016": Path("data") / "area_construida_futrono_2015-2016.geojson",
    "construida_2025": Path("data") / "area_construida_futrono_2024-2025.geojson",
    "localidades": Path("data") / "tasa_crecimiento_localidades_futrono.geojson",
}

COLORES_CLASIFICACION = {
    "Decrecimiento alto": "#FFF5EB",
    "Decrecimiento moderado": "#FDD2A5",
    "Sin crecimiento": "#FD9243",
    "Crecimiento moderado": "#DF5005",
    "Crecimiento alto": "#7F2704",
}

ORDEN_CLASES = [
    "Decrecimiento alto",
    "Decrecimiento moderado",
    "Sin crecimiento",
    "Crecimiento moderado",
    "Crecimiento alto",
]

# Rangos exactos del QML (OrRd graduado, método Quantile)
RANGOS_QML = [-1400.0, -50.0, -5.0, 5.0, 30.0, 85.549]

MAPEO_RANGOS_COLOR = [
    ("Decrecimiento alto", "#FFF5EB"),
    ("Decrecimiento moderado", "#FDD2A5"),
    ("Sin crecimiento", "#FD9243"),
    ("Crecimiento moderado", "#DF5005"),
    ("Crecimiento alto", "#7F2704"),
]


def cargar_datos(rutas=None):
    if rutas is None:
        rutas = RUTAS
    a_2016 = gpd.read_file(rutas["construida_2016"])
    a_2025 = gpd.read_file(rutas["construida_2025"])
    loc = gpd.read_file(rutas["localidades"])
    if a_2016.crs != loc.crs:
        a_2016 = a_2016.to_crs(loc.crs)
    if a_2025.crs != loc.crs:
        a_2025 = a_2025.to_crs(loc.crs)
    return a_2016, a_2025, loc


def area_por_localidad(poligonos, localidades):
    unidas = gpd.sjoin(poligonos, localidades, how="inner", predicate="intersects")
    unidas = unidas.copy()
    unidas["area_parcial"] = unidas.geometry.area
    agrupado = unidas.groupby("LOCALIDAD").agg(
        area_total=("area_parcial", "sum"),
        cantidad=("area_parcial", "count"),
    ).reset_index()
    return agrupado


def procesar_datos(a_2016, a_2025, localidades):
    porc_2016 = area_por_localidad(a_2016, localidades)
    porc_2025 = area_por_localidad(a_2025, localidades)
    merged = porc_2016.merge(
        porc_2025, on="LOCALIDAD", how="outer",
        suffixes=("_2016", "_2025")
    ).fillna(0)
    merged["diferencia_relativa"] = np.where(
        merged["area_total_2016"] > 0,
        (merged["area_total_2025"] - merged["area_total_2016"]) / merged["area_total_2016"] * 100,
        np.where(
            merged["area_total_2025"] > 0, 100, 0
        )
    )
    return merged


def clasificar(df):
    result = df.copy()
    result["clasificacion"] = pd.cut(
        result["diferencia_relativa"],
        bins=[-np.inf, -50, -5, 5, 30, np.inf],
        labels=[
            "Decrecimiento alto",
            "Decrecimiento moderado",
            "Sin crecimiento",
            "Crecimiento moderado",
            "Crecimiento alto",
        ],
    )
    result["clase_color"] = result["clasificacion"].map(COLORES_CLASIFICACION)
    return result


def flujo_completo():
    a_2016, a_2025, loc = cargar_datos()
    df = procesar_datos(a_2016, a_2025, loc)
    df = clasificar(df)
    df["LOCALIDAD"] = df["LOCALIDAD"].astype(str).str.strip()
    return df.sort_values("diferencia_relativa", ascending=False)


# ── Gráficos ────────────────────────────────────────────────────

def grafico_barras_crecimiento(df, ax=None):
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 6))
    colores = df["clase_color"].values
    ax.barh(range(len(df)), df["diferencia_relativa"].values, color=colores, edgecolor="white")
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["LOCALIDAD"].values, fontsize=8)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Diferencia relativa (%)")
    ax.set_title("Crecimiento relativo por localidad")
    return ax


def grafico_pie_clasificacion(df, ax=None):
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 6))
    conteo = df["clasificacion"].value_counts()
    colores = [COLORES_CLASIFICACION[c] for c in conteo.index]
    ax.pie(
        conteo.values, labels=conteo.index, autopct="%1.1f%%",
        colors=colores, startangle=90, wedgeprops={"edgecolor": "white"},
    )
    ax.set_title("Distribución de categorías de crecimiento")
    return ax


def grafico_histograma(df, ax=None):
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 4))
    bins = [-np.inf, -50, -5, 5, 30, np.inf]
    etiquetas = ["Decrec.\nalto", "Decrec.\nmoderado", "Sin\ncrec.", "Crec.\nmoderado", "Crec.\nalto"]
    colores_bins = ["#FFF5EB", "#FDD2A5", "#FD9243", "#DF5005", "#7F2704"]
    valores = df["diferencia_relativa"].values
    n, _, patches = ax.hist(valores, bins=30, color="steelblue", edgecolor="white", alpha=0.7)
    ax.set_xlabel("Diferencia relativa (%)")
    ax.set_ylabel("Frecuencia")
    ax.set_title("Histograma de crecimiento relativo")
    return ax


def grafico_area_comparativa(df, ax=None, max_items=15):
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 6))
    top = df.head(max_items)
    x = np.arange(len(top))
    ancho = 0.35
    ax.bar(x - ancho/2, top["area_total_2016"].values / 1e4, ancho, label="2015-2016", color="#c4a7cf")
    ax.bar(x + ancho/2, top["area_total_2025"].values / 1e4, ancho, label="2024-2025", color="#9b59b6")
    ax.set_xticks(x)
    ax.set_xticklabels(top["LOCALIDAD"].values, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Área (ha)")
    ax.set_title("Comparación de área construida por localidad")
    ax.legend()
    return ax


def generar_todos_los_graficos(df):
    fig_barras, ax_barras = plt.subplots(figsize=(10, 6))
    grafico_barras_crecimiento(df, ax_barras)
    plt.tight_layout()
    fig_barras.savefig("grafico_barras.png", dpi=150, bbox_inches="tight")
    plt.close(fig_barras)

    fig_pie, ax_pie = plt.subplots(figsize=(6, 6))
    grafico_pie_clasificacion(df, ax_pie)
    plt.tight_layout()
    fig_pie.savefig("grafico_pie.png", dpi=150, bbox_inches="tight")
    plt.close(fig_pie)

    fig_hist, ax_hist = plt.subplots(figsize=(8, 4))
    grafico_histograma(df, ax_hist)
    plt.tight_layout()
    fig_hist.savefig("grafico_histograma.png", dpi=150, bbox_inches="tight")
    plt.close(fig_hist)

    return {
        "barras": "grafico_barras.png",
        "pie": "grafico_pie.png",
        "histograma": "grafico_histograma.png",
    }


def estilo_qml_para_folium(valor):
    """Asigna color OrRd según rangos del QML (Quantile, diferencia_relativa)."""
    if valor is None or valor != valor:
        return "#CCCCCC"
    if valor < -50:
        return "#FFF5EB"
    elif valor < -5:
        return "#FDD2A5"
    elif valor < 5:
        return "#FD9243"
    elif valor < 30:
        return "#DF5005"
    else:
        return "#7F2704"


def leyenda_clasificacion_html():
    """HTML para leyenda graduada con colores OrRd del QML."""
    items = ""
    for clase, color in MAPEO_RANGOS_COLOR:
        items += f"""
        <div style="display:flex;align-items:center;margin:3px 0;">
          <div style="background:{color};width:18px;height:14px;
                      border:1px solid #555;margin-right:7px;
                      border-radius:2px;flex-shrink:0;"></div>
          <span style="font-size:11px;color:#222;">{clase}</span>
        </div>"""
    return f"""
    <div style="
        position: fixed; bottom: 30px; right: 10px; z-index: 1000;
        background: rgba(255,255,255,0.93);
        padding: 10px 14px; border-radius: 8px;
        border: 1px solid #bbb;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.25);
        font-family: Arial, sans-serif; min-width: 180px;">
      <b style="font-size:13px;color:#7F2704;">Crecimiento (%)</b>
      <hr style="margin:5px 0;border-color:#ddd;">
      {items}
    </div>"""


def exportar_tabla_csv(df, ruta="crecimiento_localidades.csv"):
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    return ruta


if __name__ == "__main__":
    df = flujo_completo()
    print(f"Localidades procesadas: {len(df)}")
    print(df[["LOCALIDAD", "area_total_2016", "area_total_2025", "diferencia_relativa", "clasificacion"]].to_string())
    generar_todos_los_graficos(df)
    exportar_tabla_csv(df)
    print("Gráficos y CSV generados.")
