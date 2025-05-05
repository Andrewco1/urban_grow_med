import streamlit as st
import geopandas as gpd
import pandas as pd
import pydeck as pdk
import plotly.express as px
import math

st.set_page_config(layout="wide", page_title="Dashboard Urbano", page_icon="🌆")
st.markdown("""
    <style>
        body, .stApp {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        .block-container {
            background-color: #1e1e1e;
        }
        .css-1r6slb0, .css-1dp5vir, .css-1v0mbdj, .css-1x8cf1d {
            background-color: #1e1e1e !important;
            color: #ffffff !important;
        }
        .stPlotlyChart > div:first-child {
            background-color: #1e1e1e !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🌆 Dashboard de Crecimiento Urbano por Barrios y Veredas MEDELLÍN - COLOMBIA")

# --- Cargar datos ---
@st.cache_data

def load_data():
    gdf_resultado = gpd.read_file("crecimiento_urbano_con_porcentajes_v2.shp").to_crs(epsg=4326)
    gdf_barrios = gpd.read_file("BarrioVereda.shp").to_crs(epsg=4326)
    return gdf_resultado, gdf_barrios

gdf, gdf_barrios = load_data()

# --- Sidebar: filtros encadenados ---
st.sidebar.header("🔍 Filtros")

limites_disponibles = sorted(gdf["LIMITECOMU"].dropna().unique())
limites_seleccionados = st.sidebar.multiselect("Selecciona comuna(s)", options=limites_disponibles)

gdf_comuna = gdf[gdf["LIMITECOMU"].isin(limites_seleccionados)] if limites_seleccionados else gdf.copy()
barrio_opciones = sorted(gdf_comuna["NOMBRE"].dropna().unique())
barrio_seleccionados = st.sidebar.multiselect("Selecciona barrio(s)/vereda(s)", options=barrio_opciones)

gdf_area = gdf_comuna[gdf_comuna["NOMBRE"].isin(barrio_seleccionados)] if barrio_seleccionados else gdf_comuna.copy()

min_area = float(gdf_area["area_cre_1"].min()) if not gdf_area.empty else 0.0
max_area = float(gdf_area["area_cre_1"].max()) if not gdf_area.empty else 1.0
area_range = st.sidebar.slider(
    "Filtrar por área de crecimiento (ha)",
    min_value=min_area,
    max_value=max_area,
    value=(min_area, max_area)
)

gdf_filtrado = gdf_area[
    (gdf_area["area_cre_1"] >= area_range[0]) &
    (gdf_area["area_cre_1"] <= area_range[1])
]

st.sidebar.markdown("---")


# --- Función de zoom dinámico ---
def calculate_zoom_level(bounds):
    minx, miny, maxx, maxy = bounds
    dx = abs(maxx - minx)
    dy = abs(maxy - miny)
    max_dim = max(dx, dy)
    if max_dim == 0:
        return 15
    zoom = round(8 - math.log(max_dim) / math.log(2))
    return min(max(zoom, 9), 16)

# --- Mapa 3D ---
st.subheader("📡 Mapa 3D del Crecimiento Urbano - Sentinel 2018–2024")

if gdf_filtrado.empty:
    st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados.")
else:
    layer_crecimiento = pdk.Layer(
        "GeoJsonLayer",
        data=gdf_filtrado,
        get_fill_color='[0, 200, 255, 160]',
        get_line_color='[0, 0, 0]',
        get_elevation="area_creci / 50",
        elevation_scale=1,
        extruded=True,
        pickable=True,
        auto_highlight=True,
    )

    layer_barrios = pdk.Layer(
        "GeoJsonLayer",
        data=gdf_barrios,
        get_fill_color='[100, 100, 100, 40]',
        get_line_color='[200, 200, 200]',
        line_width_min_pixels=1,
        pickable=False
    )

    bounds = gdf_filtrado.total_bounds
    lat_center = (bounds[1] + bounds[3]) / 2
    lon_center = (bounds[0] + bounds[2]) / 2
    zoom_level = calculate_zoom_level(bounds)

    view_state = pdk.ViewState(
        latitude=lat_center,
        longitude=lon_center,
        zoom=zoom_level,
        pitch=45,
    )

    r = pdk.Deck(
        layers=[layer_barrios, layer_crecimiento],
        initial_view_state=view_state,
        tooltip={"text": "{NOMBRE}\nÁrea: {area_cre_1:.2f} ha\n% crecimiento: {porcentaje:.2f}%"},
        map_style='mapbox://styles/mapbox/dark-v10'
    )

    st.pydeck_chart(r)

    # --- Gráficos ---
    barrios = gdf_filtrado[gdf_filtrado["SUBTIPO_BA"] == 1] if "SUBTIPO_BA" in gdf_filtrado.columns else gdf_filtrado
    if not barrios.empty:
        st.subheader("📊 Treemap de Barrios con Mayor Área Urbanizada")
        barrios_agg = barrios.groupby("NOMBRE")["area_cre_1"].sum().reset_index()
        fig1 = px.treemap(barrios_agg, path=["NOMBRE"], values="area_cre_1",
                          color="area_cre_1", color_continuous_scale="Teal")
        fig1.update_traces(texttemplate="%{label}<br>%{value:.2f} ha")
        fig1.update_layout(paper_bgcolor="#1e1e1e", plot_bgcolor="#1e1e1e", font_color="#FFFFFF")
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("📈 Porcentaje de crecimiento por Barrio")
        barrios_pct = barrios.groupby("NOMBRE")["porcentaje"].sum().reset_index()
        fig3 = px.bar(barrios_pct.sort_values("porcentaje", ascending=False).head(15),
                     x="porcentaje", y="NOMBRE", orientation="h",
                     color="porcentaje", color_continuous_scale="Tealgrn",
                     labels={"NOMBRE": "Barrio", "porcentaje": "% Crecimiento"})
        fig3.update_layout(yaxis={'categoryorder': 'total ascending'},
                           paper_bgcolor="#1e1e1e", plot_bgcolor="#1e1e1e", font_color="#FFFFFF")
        fig3.update_traces(texttemplate='%{x:.2f}%', textposition='auto')
        st.plotly_chart(fig3, use_container_width=True)

    veredas = gdf_filtrado[gdf_filtrado["SUBTIPO_BA"] == 2] if "SUBTIPO_BA" in gdf_filtrado.columns else gdf_filtrado
    if not veredas.empty:
        st.subheader("🌳 Treemap de Veredas con Mayor Área Urbanizada")
        veredas_agg = veredas.groupby("NOMBRE")["area_cre_1"].sum().reset_index()
        fig2 = px.treemap(veredas_agg, path=["NOMBRE"], values="area_cre_1",
                          color="area_cre_1", color_continuous_scale="Aggrnyl")
        fig2.update_traces(texttemplate="%{label}<br>%{value:.2f} ha")
        fig2.update_layout(paper_bgcolor="#1e1e1e", plot_bgcolor="#1e1e1e", font_color="#FFFFFF")
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📈 Porcentaje de crecimiento por Vereda")
        veredas_pct = veredas.groupby("NOMBRE")["porcentaje"].sum().reset_index()
        fig4 = px.bar(veredas_pct.sort_values("porcentaje", ascending=False).head(15),
                     x="porcentaje", y="NOMBRE", orientation="h",
                     color="porcentaje", color_continuous_scale="Purp",
                     labels={"NOMBRE": "Vereda", "porcentaje": "% Crecimiento"})
        fig4.update_layout(yaxis={'categoryorder': 'total ascending'},
                           paper_bgcolor="#1e1e1e", plot_bgcolor="#1e1e1e", font_color="#FFFFFF")
        fig4.update_traces(texttemplate='%{x:.2f}%', textposition='auto')
        st.plotly_chart(fig4, use_container_width=True)

st.markdown("---")
st.caption("Andrés Felipe Giraldo Albornoz -  Librerías usadas: rasterio, numpy, matplotlib  con Streamlit, Pydeck y GeoPandas")

st.markdown("""
---
### 🧰 Herramientas y Librerías Utilizadas
- **Streamlit**
- **GeoPandas**
- **Shapely**
- **Pydeck**
- **Plotly Express**
- **Pandas**
- **Math**
- **rasterio**
- **shapely**
- **json**
- **scipy**
            
            
### 📦 Datos y Análisis Espacial
- Se utilizaron imagenes satelitales de Sentinel-2 Level-2A para dos periodos de tiempo [2018-08-07] / [2024-06-01])
- Contiene datos modificados de Copernicus Sentinel 2024 procesados por el Desarrollador. © Copernicus Sentinel data 2024  ESA.
- Proyecciones espaciales: sistema UTM Zona 18N, EPSG:32618 (convertido a WGS 84 para visualización)

### ⚠️ Aviso Legal
Este dashboard y su contenido se publican únicamente con fines académicos y de divulgación técnica. 
**No representa asesoría profesional, ni recomendaciones de inversión, ni tiene fines comerciales.** 
Los resultados deben interpretarse con cautela y verificados si se requiere su uso en contextos oficiales o decisionales.
""")


