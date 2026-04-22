"""
Analisis de Impacto de Camaras Salvavidas (2019 vs 2022)
=========================================================
Compara velocidades y accidentalidad en corredores con camaras
salvavidas entre octubre 2019 (pre-camara) y octubre 2022 (post-camara).
"""
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 0. CONFIGURACION
# ============================================================
BASE_DIR = Path(__file__).resolve().parents[1]
CLEANED = BASE_DIR / "data" / "cleaned_data"
PROC_BASE = BASE_DIR / "data" / "processed_data"
PROCESSED = PROC_BASE / "camaras_salvavidas"
FIGURES = BASE_DIR / "outputs" / "figures" / "camaras_salvavidas"
TABLES = BASE_DIR / "outputs" / "tables" / "camaras_salvavidas"

for d in [PROCESSED, FIGURES, TABLES]:
    d.mkdir(parents=True, exist_ok=True)

UMBRAL_GRADOS = 0.005  # ~500m
plt.rcParams.update({'figure.figsize': (14, 7), 'font.size': 11, 'axes.titlesize': 14, 'axes.labelsize': 12})
sns.set_style("whitegrid")

# ============================================================
# 1. CARGA DE DATOS
# ============================================================
print("=" * 60)
print("1. CARGA DE DATOS")
print("=" * 60)

camaras = pd.read_csv(CLEANED / "camaras_salvavidas" / "tabla_camaras_salvavidas_clean.csv")
print(f"   Camaras cargadas: {len(camaras)}")

vel_2019 = pd.read_csv(PROC_BASE / "velocidad y siniestralidad 2019" / "velocidades_2019_horario.csv")
vel_2022 = pd.read_csv(PROC_BASE / "velocidad y siniestralidad 2022" / "velocidades_2022_horario.csv")
print(f"   Velocidades 2019: {len(vel_2019):,} | 2022: {len(vel_2022):,}")

sini_2019 = pd.read_csv(PROC_BASE / "velocidad y siniestralidad 2019" / "siniestralidad_con_velocidad_2019.csv")
sini_2022 = pd.read_csv(PROC_BASE / "velocidad y siniestralidad 2022" / "siniestralidad_con_velocidad_2022.csv")
print(f"   Siniestralidad 2019: {len(sini_2019):,} | 2022: {len(sini_2022):,}")

# ============================================================
# 2. DEDUPLICACION DE CAMARAS
# ============================================================
print("\n" + "=" * 60)
print("2. DEDUPLICACION DE CAMARAS")
print("=" * 60)

# Agrupar por corredor principal, tomando centroide de las camaras en cada corredor
cam_por_corredor = camaras.groupby('corredor_principal').agg(
    lat_centro=('latitud', 'mean'),
    lon_centro=('longitud', 'mean'),
    n_camaras=('id_camara', 'count'),
    vel_maxima=('velocidad_maxima', 'max'),
    localidades=('localidad', lambda x: ', '.join(x.unique())),
).reset_index()

# Tambien mantener ubicaciones individuales deduplicadas para cruce fino
cam_ubic = camaras.drop_duplicates(subset=['latitud', 'longitud']).copy()
cam_ubic = cam_ubic[['id_camara', 'corredor_principal', 'via_secundaria',
                      'latitud', 'longitud', 'velocidad_maxima', 'localidad']].reset_index(drop=True)

print(f"   Corredores con camaras: {len(cam_por_corredor)}")
print(f"   Ubicaciones unicas: {len(cam_ubic)}")

# ============================================================
# 3. CRUCE ESPACIAL: CAMARAS <-> TIDs DE VELOCIDAD
# ============================================================
print("\n" + "=" * 60)
print("3. CRUCE ESPACIAL: CAMARAS <-> TIDs")
print("=" * 60)

def asignar_tids_cercanos(cam_df, vel_df, anio_label):
    """Asigna TIDs cercanos a cada ubicacion de camara."""
    tid_centroides = vel_df.groupby('TID').agg(
        lat=('lat', 'first'), lon=('lon', 'first'),
        name_from=('name_from', 'first'), name_to=('name_to', 'first'),
    ).reset_index()

    tree = cKDTree(tid_centroides[['lat', 'lon']].values)
    coords = cam_df[['latitud', 'longitud']].values
    dist, idx = tree.query(coords)

    result = cam_df.copy()
    result[f'TID_{anio_label}'] = tid_centroides.iloc[idx]['TID'].values
    result[f'dist_m_{anio_label}'] = dist * 111_000
    result[f'name_from_{anio_label}'] = tid_centroides.iloc[idx]['name_from'].values
    result[f'name_to_{anio_label}'] = tid_centroides.iloc[idx]['name_to'].values
    result[f'match_{anio_label}'] = dist <= UMBRAL_GRADOS

    matcheados = result[f'match_{anio_label}'].sum()
    print(f"   {anio_label}: {matcheados}/{len(cam_df)} camaras matcheadas (<=500m)")
    return result

cam_cruce = asignar_tids_cercanos(cam_ubic, vel_2019, '2019')
cam_cruce = asignar_tids_cercanos(cam_cruce, vel_2022, '2022')
cam_cruce.to_csv(PROCESSED / "camaras_con_tid.csv", index=False, encoding='utf-8-sig')

# ============================================================
# 4. CRUCE ESPACIAL: CAMARAS <-> ACCIDENTES
# ============================================================
print("\n" + "=" * 60)
print("4. CRUCE ESPACIAL: CAMARAS <-> ACCIDENTES")
print("=" * 60)

def asignar_accidentes_cercanos(cam_df, sini_df, anio_label):
    """Asigna cada accidente a la camara mas cercana (si <=500m)."""
    sini_valid = sini_df.dropna(subset=['Latitud', 'Longitud']).copy()
    tree = cKDTree(cam_df[['latitud', 'longitud']].values)
    coords = sini_valid[['Latitud', 'Longitud']].values
    dist, idx = tree.query(coords)

    sini_valid['cam_idx'] = idx
    sini_valid['dist_camara_m'] = dist * 111_000
    sini_valid['cerca_camara'] = dist <= UMBRAL_GRADOS
    sini_valid['corredor_camara'] = cam_df.iloc[idx]['corredor_principal'].values
    sini_valid['id_camara_cercana'] = cam_df.iloc[idx]['id_camara'].values

    cerca = sini_valid[sini_valid['cerca_camara']].copy()
    print(f"   {anio_label}: {len(cerca)} accidentes cerca de camaras (de {len(sini_valid)} total)")
    return cerca

acc_cerca_2019 = asignar_accidentes_cercanos(cam_ubic, sini_2019, '2019')
acc_cerca_2022 = asignar_accidentes_cercanos(cam_ubic, sini_2022, '2022')

acc_cerca_2019['anio'] = 2019
acc_cerca_2022['anio'] = 2022
acc_cerca_all = pd.concat([acc_cerca_2019, acc_cerca_2022], ignore_index=True)
acc_cerca_all.to_csv(PROCESSED / "accidentes_cerca_camaras.csv", index=False, encoding='utf-8-sig')

# ============================================================
# 5. COMPARATIVA DE VELOCIDADES
# ============================================================
print("\n" + "=" * 60)
print("5. COMPARATIVA DE VELOCIDADES")
print("=" * 60)

# Obtener TIDs matcheados por ano
tids_2019 = cam_cruce.loc[cam_cruce['match_2019'], 'TID_2019'].unique()
tids_2022 = cam_cruce.loc[cam_cruce['match_2022'], 'TID_2022'].unique()

vel_cam_2019 = vel_2019[vel_2019['TID'].isin(tids_2019)].copy()
vel_cam_2022 = vel_2022[vel_2022['TID'].isin(tids_2022)].copy()

# Agregar info de corredor de camara
tid_to_corredor_2019 = cam_cruce.loc[cam_cruce['match_2019'], ['TID_2019', 'corredor_principal']].drop_duplicates()
tid_to_corredor_2022 = cam_cruce.loc[cam_cruce['match_2022'], ['TID_2022', 'corredor_principal']].drop_duplicates()

vel_cam_2019 = vel_cam_2019.merge(tid_to_corredor_2019, left_on='TID', right_on='TID_2019', how='left')
vel_cam_2022 = vel_cam_2022.merge(tid_to_corredor_2022, left_on='TID', right_on='TID_2022', how='left')

# 5.1 Perfil horario
perfil_2019 = vel_cam_2019.groupby('hora')['vel_promedio_hora'].mean().reset_index()
perfil_2019.columns = ['hora', 'vel_2019']
perfil_2022 = vel_cam_2022.groupby('hora')['vel_promedio_hora'].mean().reset_index()
perfil_2022.columns = ['hora', 'vel_2022']

comp_hora = perfil_2019.merge(perfil_2022, on='hora', how='outer').sort_values('hora')
comp_hora['delta_vel'] = comp_hora['vel_2022'] - comp_hora['vel_2019']
comp_hora['delta_pct'] = (comp_hora['delta_vel'] / comp_hora['vel_2019'] * 100).round(1)
comp_hora.to_csv(TABLES / "comparativa_velocidad_por_hora.csv", index=False)

print(f"   Vel. promedio 2019: {vel_cam_2019['vel_promedio_hora'].mean():.1f} km/h")
print(f"   Vel. promedio 2022: {vel_cam_2022['vel_promedio_hora'].mean():.1f} km/h")

# 5.2 Por corredor principal
def vel_por_corredor(vel_df, label):
    return vel_df.groupby('corredor_principal')['vel_promedio_hora'].mean().reset_index().rename(
        columns={'vel_promedio_hora': f'vel_{label}'})

comp_corredor = vel_por_corredor(vel_cam_2019, '2019').merge(
    vel_por_corredor(vel_cam_2022, '2022'), on='corredor_principal', how='outer')
comp_corredor['delta_vel'] = comp_corredor['vel_2022'] - comp_corredor['vel_2019']
comp_corredor['delta_pct'] = (comp_corredor['delta_vel'] / comp_corredor['vel_2019'] * 100).round(1)
comp_corredor = comp_corredor.sort_values('delta_vel')
comp_corredor.to_csv(TABLES / "comparativa_velocidad_por_corredor.csv", index=False)
print(f"   Corredores con datos ambos anios: {comp_corredor.dropna().shape[0]}")

# ============================================================
# 6. COMPARATIVA DE SINIESTRALIDAD
# ============================================================
print("\n" + "=" * 60)
print("6. COMPARATIVA DE SINIESTRALIDAD")
print("=" * 60)

# Dias en octubre
DIAS_2019 = 31
DIAS_2022 = 31

# 6.1 Por corredor
acc_corr_2019 = acc_cerca_2019.groupby('corredor_camara').size().reset_index(name='acc_2019')
acc_corr_2022 = acc_cerca_2022.groupby('corredor_camara').size().reset_index(name='acc_2022')
comp_acc_corr = acc_corr_2019.merge(acc_corr_2022, left_on='corredor_camara', right_on='corredor_camara', how='outer').fillna(0)
comp_acc_corr['delta_acc'] = comp_acc_corr['acc_2022'] - comp_acc_corr['acc_2019']
comp_acc_corr['tasa_dia_2019'] = (comp_acc_corr['acc_2019'] / DIAS_2019).round(2)
comp_acc_corr['tasa_dia_2022'] = (comp_acc_corr['acc_2022'] / DIAS_2022).round(2)
comp_acc_corr = comp_acc_corr.sort_values('delta_acc')
comp_acc_corr.to_csv(TABLES / "comparativa_accidentes_por_corredor.csv", index=False)

print(f"   Accidentes cerca de camaras 2019: {len(acc_cerca_2019)}")
print(f"   Accidentes cerca de camaras 2022: {len(acc_cerca_2022)}")
print(f"   Tasa diaria 2019: {len(acc_cerca_2019)/DIAS_2019:.1f} | 2022: {len(acc_cerca_2022)/DIAS_2022:.1f}")

# 6.2 Por gravedad
grav_2019 = acc_cerca_2019['Gravedad_Indicador_Tradicional'].value_counts().reset_index()
grav_2019.columns = ['gravedad', 'acc_2019']
grav_2022 = acc_cerca_2022['Gravedad_Indicador_Tradicional'].value_counts().reset_index()
grav_2022.columns = ['gravedad', 'acc_2022']
comp_grav = grav_2019.merge(grav_2022, on='gravedad', how='outer').fillna(0)
comp_grav['delta'] = comp_grav['acc_2022'] - comp_grav['acc_2019']
comp_grav['pct_2019'] = (comp_grav['acc_2019'] / comp_grav['acc_2019'].sum() * 100).round(1)
comp_grav['pct_2022'] = (comp_grav['acc_2022'] / comp_grav['acc_2022'].sum() * 100).round(1)
comp_grav.to_csv(TABLES / "comparativa_accidentes_por_gravedad.csv", index=False)

# 6.3 Por hora
acc_hora_2019 = acc_cerca_2019.groupby('Hora_Acc').size().reset_index(name='acc_2019')
acc_hora_2022 = acc_cerca_2022.groupby('Hora_Acc').size().reset_index(name='acc_2022')
comp_acc_hora = acc_hora_2019.merge(acc_hora_2022, on='Hora_Acc', how='outer').fillna(0).sort_values('Hora_Acc')
comp_acc_hora.to_csv(TABLES / "comparativa_accidentes_por_hora.csv", index=False)

# 6.4 Resumen general
resumen = pd.DataFrame({
    'metrica': [
        'Camaras totales', 'Ubicaciones unicas', 'Corredores principales',
        'Accidentes cerca camaras 2019', 'Accidentes cerca camaras 2022',
        'Tasa diaria 2019', 'Tasa diaria 2022',
        'Vel. promedio corredores camara 2019 (km/h)',
        'Vel. promedio corredores camara 2022 (km/h)',
        'Delta vel. promedio (km/h)',
    ],
    'valor': [
        len(camaras), len(cam_ubic), len(cam_por_corredor),
        len(acc_cerca_2019), len(acc_cerca_2022),
        round(len(acc_cerca_2019)/DIAS_2019, 1), round(len(acc_cerca_2022)/DIAS_2022, 1),
        round(vel_cam_2019['vel_promedio_hora'].mean(), 1),
        round(vel_cam_2022['vel_promedio_hora'].mean(), 1),
        round(vel_cam_2022['vel_promedio_hora'].mean() - vel_cam_2019['vel_promedio_hora'].mean(), 1),
    ]
})
resumen.to_csv(TABLES / "resumen_impacto_camaras.csv", index=False)
print("   [OK] Tablas resumen guardadas")

# ============================================================
# 7. VISUALIZACIONES
# ============================================================
print("\n" + "=" * 60)
print("7. VISUALIZACIONES")
print("=" * 60)

COLOR_2019 = '#e74c3c'
COLOR_2022 = '#3498db'

# 7.1 Perfil horario velocidad 2019 vs 2022
fig, ax = plt.subplots(figsize=(14, 7))
ax.plot(comp_hora['hora'], comp_hora['vel_2019'], color=COLOR_2019, linewidth=2.5,
        marker='o', markersize=7, label='2019 (pre-camara)')
ax.plot(comp_hora['hora'], comp_hora['vel_2022'], color=COLOR_2022, linewidth=2.5,
        marker='s', markersize=7, label='2022 (post-camara)')
ax.fill_between(comp_hora['hora'], comp_hora['vel_2019'], comp_hora['vel_2022'],
                alpha=0.15, color='gray')
ax.set_xlabel('Hora del dia')
ax.set_ylabel('Velocidad promedio (km/h)')
ax.set_title('Velocidad Promedio en Corredores con Camaras Salvavidas\n2019 (pre) vs 2022 (post)')
ax.set_xticks(range(24))
ax.legend(fontsize=12)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(FIGURES / "comparativa_vel_hora_2019_2022.png", dpi=150, bbox_inches='tight')
plt.close()
print("   [OK] comparativa_vel_hora_2019_2022.png")

# 7.2 Velocidad por corredor (barras agrupadas)
comp_both = comp_corredor.dropna(subset=['vel_2019', 'vel_2022']).copy()
if len(comp_both) > 0:
    comp_both = comp_both.sort_values('vel_2019', ascending=True)
    fig, ax = plt.subplots(figsize=(14, max(8, len(comp_both) * 0.5)))
    y = np.arange(len(comp_both))
    h = 0.35
    ax.barh(y - h/2, comp_both['vel_2019'], h, color=COLOR_2019, alpha=0.8, label='2019')
    ax.barh(y + h/2, comp_both['vel_2022'], h, color=COLOR_2022, alpha=0.8, label='2022')
    ax.set_yticks(y)
    ax.set_yticklabels(comp_both['corredor_principal'])
    ax.set_xlabel('Velocidad promedio (km/h)')
    ax.set_title('Velocidad Promedio por Corredor con Camaras - 2019 vs 2022')
    ax.legend(fontsize=12)
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES / "comparativa_vel_corredor.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("   [OK] comparativa_vel_corredor.png")

# 7.3 Delta de velocidad por corredor
if len(comp_both) > 0:
    comp_sorted = comp_both.sort_values('delta_vel')
    fig, ax = plt.subplots(figsize=(14, max(8, len(comp_sorted) * 0.5)))
    colors = ['#2ecc71' if d < 0 else '#e74c3c' for d in comp_sorted['delta_vel']]
    ax.barh(comp_sorted['corredor_principal'], comp_sorted['delta_vel'], color=colors, alpha=0.8)
    ax.axvline(0, color='black', linewidth=0.8)
    ax.set_xlabel('Cambio de velocidad (km/h) [2022 - 2019]')
    ax.set_title('Cambio de Velocidad en Corredores con Camaras Salvavidas\nVerde = reduccion | Rojo = aumento')
    for i, (_, row) in enumerate(comp_sorted.iterrows()):
        pct = row['delta_pct']
        ax.annotate(f'{pct:+.1f}%', (row['delta_vel'], i),
                    ha='left' if row['delta_vel'] >= 0 else 'right',
                    va='center', fontsize=9, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES / "delta_velocidad_corredor.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("   [OK] delta_velocidad_corredor.png")

# 7.4 Accidentes por corredor (barras agrupadas)
comp_acc_both = comp_acc_corr[(comp_acc_corr['acc_2019'] > 0) | (comp_acc_corr['acc_2022'] > 0)].copy()
comp_acc_both = comp_acc_both.sort_values('acc_2019', ascending=True)
if len(comp_acc_both) > 0:
    fig, ax = plt.subplots(figsize=(14, max(8, len(comp_acc_both) * 0.5)))
    y = np.arange(len(comp_acc_both))
    h = 0.35
    ax.barh(y - h/2, comp_acc_both['acc_2019'], h, color=COLOR_2019, alpha=0.8, label='2019')
    ax.barh(y + h/2, comp_acc_both['acc_2022'], h, color=COLOR_2022, alpha=0.8, label='2022')
    ax.set_yticks(y)
    ax.set_yticklabels(comp_acc_both['corredor_camara'])
    ax.set_xlabel('Numero de accidentes')
    ax.set_title('Accidentes Cerca de Camaras Salvavidas por Corredor - 2019 vs 2022')
    ax.legend(fontsize=12)
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES / "comparativa_accidentes_corredor.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("   [OK] comparativa_accidentes_corredor.png")

# 7.5 Accidentes por gravedad (barras agrupadas)
fig, ax = plt.subplots(figsize=(10, 6))
x = np.arange(len(comp_grav))
w = 0.35
ax.bar(x - w/2, comp_grav['acc_2019'], w, color=COLOR_2019, alpha=0.8, label='2019')
ax.bar(x + w/2, comp_grav['acc_2022'], w, color=COLOR_2022, alpha=0.8, label='2022')
ax.set_xticks(x)
ax.set_xticklabels(comp_grav['gravedad'], rotation=15)
ax.set_ylabel('Numero de accidentes')
ax.set_title('Accidentes Cerca de Camaras por Gravedad - 2019 vs 2022')
ax.legend(fontsize=12)
# Agregar porcentajes sobre barras
for i, row in comp_grav.iterrows():
    ax.annotate(f"{row['pct_2019']:.0f}%", (i - w/2, row['acc_2019'] + 2),
                ha='center', fontsize=9, color=COLOR_2019)
    ax.annotate(f"{row['pct_2022']:.0f}%", (i + w/2, row['acc_2022'] + 2),
                ha='center', fontsize=9, color=COLOR_2022)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(FIGURES / "comparativa_accidentes_gravedad.png", dpi=150, bbox_inches='tight')
plt.close()
print("   [OK] comparativa_accidentes_gravedad.png")

# 7.6 Accidentes por hora (lineas superpuestas)
fig, ax = plt.subplots(figsize=(14, 7))
ax.plot(comp_acc_hora['Hora_Acc'], comp_acc_hora['acc_2019'], color=COLOR_2019,
        linewidth=2.5, marker='o', markersize=7, label='2019')
ax.plot(comp_acc_hora['Hora_Acc'], comp_acc_hora['acc_2022'], color=COLOR_2022,
        linewidth=2.5, marker='s', markersize=7, label='2022')
ax.fill_between(comp_acc_hora['Hora_Acc'], comp_acc_hora['acc_2019'], alpha=0.1, color=COLOR_2019)
ax.fill_between(comp_acc_hora['Hora_Acc'], comp_acc_hora['acc_2022'], alpha=0.1, color=COLOR_2022)
ax.set_xlabel('Hora del dia')
ax.set_ylabel('Numero de accidentes')
ax.set_title('Accidentes Cerca de Camaras Salvavidas por Hora - 2019 vs 2022')
ax.set_xticks(range(24))
ax.legend(fontsize=12)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(FIGURES / "comparativa_accidentes_hora.png", dpi=150, bbox_inches='tight')
plt.close()
print("   [OK] comparativa_accidentes_hora.png")

# ============================================================
# 8. REPORTE FINAL
# ============================================================
print("\n" + "=" * 60)
print("8. REPORTE FINAL")
print("=" * 60)
print(f"   Camaras: {len(camaras)} total, {len(cam_ubic)} ubicaciones, {len(cam_por_corredor)} corredores")
print(f"   Accidentes cerca camaras: 2019={len(acc_cerca_2019)} | 2022={len(acc_cerca_2022)}")
print(f"   Tasa diaria: 2019={len(acc_cerca_2019)/DIAS_2019:.1f} | 2022={len(acc_cerca_2022)/DIAS_2022:.1f}")
print(f"   Vel. promedio corredores camara: 2019={vel_cam_2019['vel_promedio_hora'].mean():.1f} | 2022={vel_cam_2022['vel_promedio_hora'].mean():.1f} km/h")
print(f"\n   Archivos en:")
print(f"      {PROCESSED}")
print(f"      {TABLES}")
print(f"      {FIGURES}")
print("\n   [OK] Proceso completado exitosamente")
