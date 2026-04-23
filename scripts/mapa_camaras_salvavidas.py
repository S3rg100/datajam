# -*- coding: utf-8 -*-
"""
=============================================================================
  MAPA INTERACTIVO + DATASETS PARA POWER BI - Cámaras Salvavidas Bogotá
=============================================================================
  Genera los datasets finales para el tablero de Power BI y un mapa
  interactivo HTML con Folium para visualización geoespacial del impacto.

  ENTRADAS:
    data/cleaned_data/camaras_salvavidas/tabla_camaras_salvavidas_clean.csv
    data/processed_data/camaras_salvavidas/camaras_con_tid.csv
    data/processed_data/camaras_salvavidas/accidentes_cerca_camaras.csv
    data/cleaned_data/velocidades/velocidades_2019_final.csv
    data/cleaned_data/velocidades/velocidades_2022_final.csv

  SALIDAS:
    data/processed_data/camaras_salvavidas/
      - dataset_camaras_mapa.csv              → Dim_Camaras (85 registros, 22 cols)
      - dataset_accidentes_cerca_camaras_mapa.csv → Fact_Accidentes (817 registros)
      - dataset_velocidades_horario_camaras.csv   → Fact_Velocidades (1,032 registros)
    outputs/figures/camaras_salvavidas/
      - mapa_camaras_salvavidas.html          → Mapa interactivo Folium

  FORMATO DE SALIDA CSV:
    Los archivos CSV usan punto y coma (;) como separador de columnas y
    coma (,) como separador decimal, para compatibilidad directa con
    Power BI en configuración regional en español (Colombia).

  MODELO DE DATOS POWER BI:
    Dim_Camaras (centro) ──1:*──► Fact_Accidentes  (por id_camara)
    Dim_Camaras (centro) ──*:*──► Fact_Velocidades (por corredor_principal)
=============================================================================
"""
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
from pathlib import Path
import folium
from folium.plugins import MarkerCluster
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 0. CONFIGURACION
# ============================================================
BASE_DIR = Path(__file__).resolve().parents[1]
CLEANED = BASE_DIR / "data" / "cleaned_data"
PROC_BASE = BASE_DIR / "data" / "processed_data"
OUTPUT = PROC_BASE / "camaras_salvavidas"
FIGURES = BASE_DIR / "outputs" / "figures" / "camaras_salvavidas"

OUTPUT.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

UMBRAL_GRADOS = 0.005  # ~500m

# ============================================================
# 1. CARGA DE DATOS
# ============================================================
print("=" * 60)
print("1. CARGA DE DATOS")
print("=" * 60)

camaras = pd.read_csv(CLEANED / "camaras_salvavidas" / "tabla_camaras_salvavidas_clean.csv")
vel_2019 = pd.read_csv(PROC_BASE / "velocidad y siniestralidad 2019" / "velocidades_2019_horario.csv")
vel_2022 = pd.read_csv(PROC_BASE / "velocidad y siniestralidad 2022" / "velocidades_2022_horario.csv")
acc_cerca = pd.read_csv(PROC_BASE / "camaras_salvavidas" / "accidentes_cerca_camaras.csv")
cam_tid = pd.read_csv(PROC_BASE / "camaras_salvavidas" / "camaras_con_tid.csv")

print(f"   Camaras: {len(camaras)} | Accidentes cerca: {len(acc_cerca)}")

# ============================================================
# 2. DATASET CONSOLIDADO PARA POWER BI
# ============================================================
print("\n" + "=" * 60)
print("2. DATASET CONSOLIDADO PARA POWER BI")
print("=" * 60)

# --- 2.1 Tabla: Camaras con metricas por ubicacion ---
# Agrupar camaras que comparten misma ubicacion (sentido N-S / S-N)
cam_ubic = cam_tid.copy()

# Para cada camara, calcular vel promedio del TID asignado (por anio)
def vel_promedio_tid(vel_df, tids):
    """Velocidad promedio general de un conjunto de TIDs."""
    return vel_df[vel_df['TID'].isin(tids)].groupby('TID')['vel_promedio_hora'].mean()

vel_mean_2019 = vel_promedio_tid(vel_2019, cam_ubic['TID_2019'].dropna().unique())
vel_mean_2022 = vel_promedio_tid(vel_2022, cam_ubic['TID_2022'].dropna().unique())

cam_ubic['vel_promedio_2019'] = cam_ubic['TID_2019'].map(vel_mean_2019)
cam_ubic['vel_promedio_2022'] = cam_ubic['TID_2022'].map(vel_mean_2022)
cam_ubic['delta_vel'] = cam_ubic['vel_promedio_2022'] - cam_ubic['vel_promedio_2019']
cam_ubic['delta_vel_pct'] = (cam_ubic['delta_vel'] / cam_ubic['vel_promedio_2019'] * 100).round(1)

# Accidentes por camara por anio
acc_por_cam_anio = acc_cerca.groupby(['id_camara_cercana', 'anio']).agg(
    num_accidentes=('Codigo_Accidente', 'count'),
    acc_con_heridos=('Gravedad_Indicador_Tradicional', lambda x: (x == 'Con Heridos').sum()),
    acc_con_muertos=('Gravedad_Indicador_Tradicional', lambda x: (x == 'Con Muertos').sum()),
    acc_solo_danos=('Gravedad_Indicador_Tradicional', lambda x: (x == 'Solo Daños').sum()),
).reset_index()

acc_2019 = acc_por_cam_anio[acc_por_cam_anio['anio'] == 2019].rename(
    columns={c: f'{c}_2019' for c in ['num_accidentes', 'acc_con_heridos', 'acc_con_muertos', 'acc_solo_danos']})
acc_2022 = acc_por_cam_anio[acc_por_cam_anio['anio'] == 2022].rename(
    columns={c: f'{c}_2022' for c in ['num_accidentes', 'acc_con_heridos', 'acc_con_muertos', 'acc_solo_danos']})

cam_ubic = cam_ubic.merge(acc_2019.drop(columns=['anio']), left_on='id_camara', right_on='id_camara_cercana', how='left').drop(columns=['id_camara_cercana'])
cam_ubic = cam_ubic.merge(acc_2022.drop(columns=['anio']), left_on='id_camara', right_on='id_camara_cercana', how='left').drop(columns=['id_camara_cercana'])

# Rellenar NaN con 0
for col in ['num_accidentes_2019', 'num_accidentes_2022',
            'acc_con_heridos_2019', 'acc_con_heridos_2022',
            'acc_con_muertos_2019', 'acc_con_muertos_2022',
            'acc_solo_danos_2019', 'acc_solo_danos_2022']:
    if col in cam_ubic.columns:
        cam_ubic[col] = cam_ubic[col].fillna(0).astype(int)

cam_ubic['delta_accidentes'] = cam_ubic.get('num_accidentes_2022', 0) - cam_ubic.get('num_accidentes_2019', 0)

# Limpiar columnas para Power BI
cols_powerbi = [
    'id_camara', 'corredor_principal', 'via_secundaria', 'latitud', 'longitud',
    'velocidad_maxima', 'localidad',
    'vel_promedio_2019', 'vel_promedio_2022', 'delta_vel', 'delta_vel_pct',
    'num_accidentes_2019', 'num_accidentes_2022', 'delta_accidentes',
    'acc_con_heridos_2019', 'acc_con_heridos_2022',
    'acc_con_muertos_2019', 'acc_con_muertos_2022',
    'acc_solo_danos_2019', 'acc_solo_danos_2022',
    'match_2019', 'match_2022',
]
cols_exist = [c for c in cols_powerbi if c in cam_ubic.columns]
dataset_camaras = cam_ubic[cols_exist].copy()
dataset_camaras.to_csv(OUTPUT / "dataset_camaras_mapa.csv", index=False, encoding='utf-8-sig', sep=';', decimal=',')
print(f"   dataset_camaras_mapa.csv: {len(dataset_camaras)} registros, {len(cols_exist)} columnas")

# --- 2.2 Tabla: Accidentes individuales (para mapa de puntos) ---
cols_acc = [
    'Codigo_Accidente', 'Latitud', 'Longitud', 'Hora_Acc', 'Dia_Semana_Acc',
    'Clase_Acc', 'Gravedad_Indicador_Tradicional', 'Localidad',
    'corredor_camara', 'id_camara_cercana', 'dist_camara_m', 'anio',
]
cols_acc_exist = [c for c in cols_acc if c in acc_cerca.columns]
dataset_accidentes = acc_cerca[cols_acc_exist].copy()
dataset_accidentes.to_csv(OUTPUT / "dataset_accidentes_cerca_camaras_mapa.csv", index=False, encoding='utf-8-sig', sep=';', decimal=',')
print(f"   dataset_accidentes_cerca_camaras_mapa.csv: {len(dataset_accidentes)} registros")

# --- 2.3 Tabla: Velocidades por hora en corredores con camara (para graficos temporales) ---
tids_2019 = cam_ubic.loc[cam_ubic['match_2019'] == True, 'TID_2019'].dropna().unique()
tids_2022 = cam_ubic.loc[cam_ubic['match_2022'] == True, 'TID_2022'].dropna().unique()

# Mapear TID a corredor principal
tid_corr_2019 = cam_ubic.loc[cam_ubic['match_2019'] == True, ['TID_2019', 'corredor_principal']].drop_duplicates()
tid_corr_2022 = cam_ubic.loc[cam_ubic['match_2022'] == True, ['TID_2022', 'corredor_principal']].drop_duplicates()

vel_h_2019 = vel_2019[vel_2019['TID'].isin(tids_2019)][['TID', 'hora', 'vel_promedio_hora']].copy()
vel_h_2019 = vel_h_2019.merge(tid_corr_2019, left_on='TID', right_on='TID_2019', how='left')
vel_h_2019['anio'] = 2019

vel_h_2022 = vel_2022[vel_2022['TID'].isin(tids_2022)][['TID', 'hora', 'vel_promedio_hora']].copy()
vel_h_2022 = vel_h_2022.merge(tid_corr_2022, left_on='TID', right_on='TID_2022', how='left')
vel_h_2022['anio'] = 2022

vel_horario_camaras = pd.concat([
    vel_h_2019[['TID', 'hora', 'vel_promedio_hora', 'corredor_principal', 'anio']],
    vel_h_2022[['TID', 'hora', 'vel_promedio_hora', 'corredor_principal', 'anio']],
], ignore_index=True)
vel_horario_camaras.to_csv(OUTPUT / "dataset_velocidades_horario_camaras.csv", index=False, encoding='utf-8-sig', sep=';', decimal=',')
print(f"   dataset_velocidades_horario_camaras.csv: {len(vel_horario_camaras)} registros")

# ============================================================
# 3. MAPA INTERACTIVO CON FOLIUM
# ============================================================
print("\n" + "=" * 60)
print("3. MAPA INTERACTIVO")
print("=" * 60)

# Centro de Bogota
CENTER_LAT = dataset_camaras['latitud'].mean()
CENTER_LON = dataset_camaras['longitud'].mean()

m = folium.Map(
    location=[CENTER_LAT, CENTER_LON],
    zoom_start=12,
    tiles='CartoDB positron',
)

# --- Capa: Camaras salvavidas ---
cam_layer = folium.FeatureGroup(name='Camaras Salvavidas')

for _, row in dataset_camaras.iterrows():
    vel19 = f"{row['vel_promedio_2019']:.1f}" if pd.notna(row.get('vel_promedio_2019')) else 'N/D'
    vel22 = f"{row['vel_promedio_2022']:.1f}" if pd.notna(row.get('vel_promedio_2022')) else 'N/D'
    delta_v = f"{row['delta_vel']:+.1f}" if pd.notna(row.get('delta_vel')) else 'N/D'
    acc19 = int(row.get('num_accidentes_2019', 0))
    acc22 = int(row.get('num_accidentes_2022', 0))
    delta_a = acc22 - acc19

    # Color basado en delta de accidentes
    if delta_a < 0:
        color = 'green'
        icon = 'arrow-down'
    elif delta_a > 0:
        color = 'red'
        icon = 'arrow-up'
    else:
        color = 'gray'
        icon = 'minus'

    popup_html = f"""
    <div style="font-family: Arial; font-size: 12px; width: 280px;">
        <h4 style="margin:0; color:#2c3e50;">{row['corredor_principal']}</h4>
        <p style="margin:2px 0; color:#7f8c8d;"><b>{row['id_camara']}</b> | {row['via_secundaria']} | Vel. max: {row['velocidad_maxima']} km/h</p>
        <hr style="margin:5px 0;">
        <table style="width:100%; border-collapse:collapse;">
            <tr style="background:#f8f9fa;"><th></th><th>2019</th><th>2022</th><th>Delta</th></tr>
            <tr><td><b>Vel. prom.</b></td><td>{vel19}</td><td>{vel22}</td><td>{delta_v} km/h</td></tr>
            <tr style="background:#f8f9fa;"><td><b>Accidentes</b></td><td>{acc19}</td><td>{acc22}</td><td style="color:{'green' if delta_a<=0 else 'red'};"><b>{delta_a:+d}</b></td></tr>
            <tr><td><b>Con heridos</b></td><td>{int(row.get('acc_con_heridos_2019',0))}</td><td>{int(row.get('acc_con_heridos_2022',0))}</td><td></td></tr>
            <tr style="background:#f8f9fa;"><td><b>Con muertos</b></td><td>{int(row.get('acc_con_muertos_2019',0))}</td><td>{int(row.get('acc_con_muertos_2022',0))}</td><td></td></tr>
        </table>
    </div>
    """

    folium.Marker(
        location=[row['latitud'], row['longitud']],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=f"{row['corredor_principal']} - {row['id_camara']}",
        icon=folium.Icon(color=color, icon='camera', prefix='fa'),
    ).add_to(cam_layer)

cam_layer.add_to(m)

# --- Capa: Accidentes 2019 ---
acc_2019_layer = folium.FeatureGroup(name='Accidentes 2019 (pre-camara)', show=False)
acc_2019_cluster = MarkerCluster().add_to(acc_2019_layer)

grav_colors = {'Solo Daños': '#f39c12', 'Con Heridos': '#e74c3c', 'Con Muertos': '#2c3e50'}

for _, row in dataset_accidentes[dataset_accidentes['anio'] == 2019].iterrows():
    grav = row.get('Gravedad_Indicador_Tradicional', 'N/A')
    color = grav_colors.get(grav, '#95a5a6')
    folium.CircleMarker(
        location=[row['Latitud'], row['Longitud']],
        radius=4,
        color=color,
        fill=True,
        fill_opacity=0.7,
        popup=f"2019 | {grav} | H:{int(row['Hora_Acc'])}h | {row.get('corredor_camara','')}",
    ).add_to(acc_2019_cluster)

acc_2019_layer.add_to(m)

# --- Capa: Accidentes 2022 ---
acc_2022_layer = folium.FeatureGroup(name='Accidentes 2022 (post-camara)', show=False)
acc_2022_cluster = MarkerCluster().add_to(acc_2022_layer)

for _, row in dataset_accidentes[dataset_accidentes['anio'] == 2022].iterrows():
    grav = row.get('Gravedad_Indicador_Tradicional', 'N/A')
    color = grav_colors.get(grav, '#95a5a6')
    folium.CircleMarker(
        location=[row['Latitud'], row['Longitud']],
        radius=4,
        color=color,
        fill=True,
        fill_opacity=0.7,
        popup=f"2022 | {grav} | H:{int(row['Hora_Acc'])}h | {row.get('corredor_camara','')}",
    ).add_to(acc_2022_cluster)

acc_2022_layer.add_to(m)

# --- Leyenda ---
legend_html = """
<div style="position:fixed; bottom:30px; left:30px; z-index:1000; background:white;
     padding:15px; border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.3);
     font-family:Arial; font-size:12px;">
    <h4 style="margin:0 0 8px 0;">Leyenda</h4>
    <p style="margin:3px 0;"><span style="color:green;">&#9679;</span> Camara: reduccion accidentes</p>
    <p style="margin:3px 0;"><span style="color:red;">&#9679;</span> Camara: aumento accidentes</p>
    <p style="margin:3px 0;"><span style="color:gray;">&#9679;</span> Camara: sin cambio</p>
    <hr style="margin:5px 0;">
    <p style="margin:3px 0;"><span style="color:#f39c12;">&#9679;</span> Accidente: Solo Danos</p>
    <p style="margin:3px 0;"><span style="color:#e74c3c;">&#9679;</span> Accidente: Con Heridos</p>
    <p style="margin:3px 0;"><span style="color:#2c3e50;">&#9679;</span> Accidente: Con Muertos</p>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Control de capas
folium.LayerControl(collapsed=False).add_to(m)

# Guardar
mapa_path = FIGURES / "mapa_camaras_salvavidas.html"
m.save(str(mapa_path))
print(f"   [OK] Mapa interactivo: {mapa_path}")

# ============================================================
# 4. RESUMEN
# ============================================================
print("\n" + "=" * 60)
print("4. RESUMEN DE ARCHIVOS")
print("=" * 60)
print("   Datasets Power BI:")
print(f"      {OUTPUT / 'dataset_camaras_mapa.csv'}")
print(f"      {OUTPUT / 'dataset_accidentes_cerca_camaras_mapa.csv'}")
print(f"      {OUTPUT / 'dataset_velocidades_horario_camaras.csv'}")
print("   Mapa interactivo:")
print(f"      {mapa_path}")
print("\n   [OK] Proceso completado")
