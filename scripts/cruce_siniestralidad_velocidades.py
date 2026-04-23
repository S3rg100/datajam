# -*- coding: utf-8 -*-
"""
=============================================================================
  CRUCE SINIESTRALIDAD × VELOCIDADES (2019 y 2022) - Bogotá D.C.
=============================================================================
  Relaciona accidentes de tránsito con velocidades promedio en corredores
  viales de Bogotá usando proximidad geográfica (KDTree) y franja horaria.

  ENTRADAS:
    data/cleaned_data/Siniestralidad/siniestralidad_clean.csv
    data/cleaned_data/velocidades/velocidades_2019_final.csv
    data/cleaned_data/velocidades/velocidades_2022_final.csv

  SALIDAS (por año):
    data/processed_data/velocidad y siniestralidad {año}/
      - siniestralidad_con_velocidad_{año}.csv  → Accidentes enriquecidos con vel.
      - velocidades_{año}_horario.csv           → Vel. promedio por TID y hora
      - velocidades_{año}_horario_dia_semana.csv → Vel. por TID, hora y día
    outputs/figures/velocidad y siniestralidad {año}/
      - 5 gráficas: distribución de distancias, mapa de calor, scatter, etc.
    outputs/tables/velocidad y siniestralidad {año}/
      - Tablas resumen por hora, corredor, gravedad

  METODOLOGÍA:
    1. Carga datos de siniestralidad y velocidades limpios.
    2. Agrega velocidades por hora para cada segmento (TID).
    3. Construye un KDTree con los centroides de los TIDs.
    4. Para cada accidente, busca el TID más cercano (≤500m ≈ 0.005°).
    5. Asocia la velocidad promedio del TID en la hora del accidente.
    6. Genera gráficas de distribución de distancias, correlaciones y
       perfiles de velocidad por gravedad del siniestro.
=============================================================================
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
PROCESSED_BASE = BASE_DIR / "data" / "processed_data"
FIGURES_BASE = BASE_DIR / "outputs" / "figures"
TABLES_BASE = BASE_DIR / "outputs" / "tables"

UMBRAL_DISTANCIA_GRADOS = 0.005  # ~500m en Bogota

plt.rcParams.update({
    'figure.figsize': (12, 7),
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
})

# Configuracion de anios a procesar
ANIOS = [
    {
        'anio': 2019,
        'vel_file': 'velocidades_2019_final.csv',
        'folder_name': 'velocidad y siniestralidad 2019',
    },
    {
        'anio': 2022,
        'vel_file': 'velocidades_2022_final.csv',
        'folder_name': 'velocidad y siniestralidad 2022',
    },
]

# ============================================================
# 1. CARGA DE SINIESTRALIDAD (comun a ambos anios)
# ============================================================
print("=" * 60)
print("CARGA DE SINIESTRALIDAD")
print("=" * 60)

siniestralidad_full = pd.read_csv(CLEANED / "Siniestralidad" / "siniestralidad_clean.csv")
print(f"   Siniestralidad total cargada: {len(siniestralidad_full):,} registros")
print(f"   Por anio: {siniestralidad_full['AA_Acc'].value_counts().to_dict()}")


def procesar_cruce(config, siniestralidad_full):
    """Procesa el cruce siniestralidad x velocidades para un anio dado."""

    anio = config['anio']
    vel_file = config['vel_file']
    folder_name = config['folder_name']

    # Rutas de salida por anio
    PROCESSED = PROCESSED_BASE / folder_name
    FIGURES = FIGURES_BASE / folder_name
    TABLES = TABLES_BASE / folder_name

    for d in [PROCESSED, FIGURES, TABLES]:
        d.mkdir(parents=True, exist_ok=True)

    print("\n" + "#" * 60)
    print(f"# PROCESANDO ANIO: {anio}")
    print("#" * 60)

    # ----------------------------------------------------------
    # 1. CARGA DE VELOCIDADES
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"1. CARGA DE VELOCIDADES {anio}")
    print("=" * 60)

    # Filtrar siniestralidad del anio correspondiente
    siniestralidad = siniestralidad_full[siniestralidad_full['AA_Acc'] == anio].copy()
    print(f"   Siniestralidad {anio}: {len(siniestralidad):,} registros")

    print(f"   Cargando velocidades {anio} (archivo grande)...")
    velocidades = pd.read_csv(CLEANED / "velocidades" / vel_file)
    print(f"   Velocidades cargada: {len(velocidades):,} registros")

    # ----------------------------------------------------------
    # 2. TRATAMIENTO DEL DATASET DE VELOCIDADES
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"2. TRATAMIENTO DE VELOCIDADES {anio}")
    print("=" * 60)

    # Extraer hora del campo CUARTO_HORA
    velocidades['hora'] = velocidades['CUARTO_HORA'].str.split(':').str[0].astype(int)

    # --- Agregacion nivel 1: TID x hora (perfil general) ---
    vel_horario = velocidades.groupby(['TID', 'hora']).agg(
        vel_promedio_hora=('VEL_PROMEDIO', 'mean'),
        vel_ponderada_hora=('VEL_PONDERADA', 'mean'),
        num_dispositivos=('NUMDISPOSITIVOS', 'sum'),
        num_registros=('VEL_PROMEDIO', 'count'),
        lat=('lat', 'first'),
        lon=('lon', 'first'),
        name_from=('NAME_FROM', 'first'),
        name_to=('NAME_TO', 'first'),
        distance_m=('DISTANCE_M', 'first'),
        confianza_geo=('confianza_geo', 'first'),
    ).reset_index()

    print(f"   Vel horario (TID x hora): {len(vel_horario):,} registros")

    # --- Agregacion nivel 2: TID x hora x dia_semana ---
    vel_horario_dia = velocidades.groupby(['TID', 'hora', 'DIA_SEMANA']).agg(
        vel_promedio_hora=('VEL_PROMEDIO', 'mean'),
        vel_ponderada_hora=('VEL_PONDERADA', 'mean'),
        num_dispositivos=('NUMDISPOSITIVOS', 'sum'),
        num_registros=('VEL_PROMEDIO', 'count'),
        lat=('lat', 'first'),
        lon=('lon', 'first'),
        name_from=('NAME_FROM', 'first'),
        name_to=('NAME_TO', 'first'),
        distance_m=('DISTANCE_M', 'first'),
        confianza_geo=('confianza_geo', 'first'),
    ).reset_index()

    print(f"   Vel horario x dia (TID x hora x dia): {len(vel_horario_dia):,} registros")

    # Guardar datasets intermedios
    vel_horario.to_csv(PROCESSED / f"velocidades_{anio}_horario.csv", index=False)
    vel_horario_dia.to_csv(PROCESSED / f"velocidades_{anio}_horario_dia_semana.csv", index=False)
    print(f"   [OK] Datasets de velocidades {anio} agregados guardados")

    # Liberar memoria del dataset original
    del velocidades

    # ----------------------------------------------------------
    # 3. CRUCE ESPACIAL
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"3. CRUCE ESPACIAL (KDTree) - {anio}")
    print("=" * 60)

    # Filtrar accidentes sin coordenadas
    sin_coords = siniestralidad[['Latitud', 'Longitud']].isnull().any(axis=1)
    print(f"   Accidentes sin coordenadas: {sin_coords.sum()}")

    sini_con_coords = siniestralidad[~sin_coords].copy()
    sini_sin_coords = siniestralidad[sin_coords].copy()

    # Construir tabla de centroides TID unicos
    tid_centroides = vel_horario.groupby('TID').agg(
        lat=('lat', 'first'),
        lon=('lon', 'first'),
        name_from=('name_from', 'first'),
        name_to=('name_to', 'first'),
        distance_m=('distance_m', 'first'),
        confianza_geo=('confianza_geo', 'first'),
    ).reset_index()

    print(f"   TIDs unicos (corredores): {len(tid_centroides)}")

    # Construir KDTree con centroides
    tree = cKDTree(tid_centroides[['lat', 'lon']].values)

    # Buscar TID mas cercano para cada accidente
    coords_acc = sini_con_coords[['Latitud', 'Longitud']].values
    distancias, indices = tree.query(coords_acc)

    # Asignar resultados
    sini_con_coords['TID_cercano'] = tid_centroides.iloc[indices]['TID'].values
    sini_con_coords['distancia_grados'] = distancias
    sini_con_coords['distancia_metros_aprox'] = distancias * 111_000
    sini_con_coords['corredor_from'] = tid_centroides.iloc[indices]['name_from'].values
    sini_con_coords['corredor_to'] = tid_centroides.iloc[indices]['name_to'].values
    sini_con_coords['lat_corredor'] = tid_centroides.iloc[indices]['lat'].values
    sini_con_coords['lon_corredor'] = tid_centroides.iloc[indices]['lon'].values

    # Aplicar umbral
    sini_con_coords['match_valido'] = sini_con_coords['distancia_grados'] <= UMBRAL_DISTANCIA_GRADOS
    matcheados = sini_con_coords['match_valido'].sum()
    no_matcheados = (~sini_con_coords['match_valido']).sum()

    print(f"   Accidentes matcheados (<=500m): {matcheados}")
    print(f"   Accidentes NO matcheados (>500m): {no_matcheados}")
    print(f"   Cobertura: {matcheados / len(sini_con_coords) * 100:.1f}%")

    # ----------------------------------------------------------
    # 4. JOIN TEMPORAL (hora)
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"4. JOIN TEMPORAL POR HORA - {anio}")
    print("=" * 60)

    # Merge con velocidad promedio por hora del TID asignado
    cruce = sini_con_coords.merge(
        vel_horario[['TID', 'hora', 'vel_promedio_hora', 'vel_ponderada_hora', 'num_dispositivos', 'num_registros']],
        left_on=['TID_cercano', 'Hora_Acc'],
        right_on=['TID', 'hora'],
        how='left'
    )

    # Limpiar columnas duplicadas
    cruce = cruce.drop(columns=['TID', 'hora'], errors='ignore')

    # Marcar registros sin velocidad
    cruce['tiene_velocidad'] = cruce['vel_promedio_hora'].notna() & cruce['match_valido']

    con_vel = cruce['tiene_velocidad'].sum()
    print(f"   Registros con velocidad asignada: {con_vel}")
    print(f"   Registros sin velocidad: {len(cruce) - con_vel}")

    # Agregar registros sin coordenadas al final
    for col in ['TID_cercano', 'distancia_grados', 'distancia_metros_aprox',
                'corredor_from', 'corredor_to', 'lat_corredor', 'lon_corredor',
                'match_valido', 'vel_promedio_hora', 'vel_ponderada_hora',
                'num_dispositivos', 'num_registros', 'tiene_velocidad']:
        if col not in sini_sin_coords.columns:
            sini_sin_coords[col] = np.nan

    cruce_final = pd.concat([cruce, sini_sin_coords], ignore_index=True)

    # Guardar dataset cruzado
    cruce_final.to_csv(PROCESSED / f"siniestralidad_con_velocidad_{anio}.csv", index=False, encoding='utf-8-sig')
    print(f"   [OK] Dataset cruzado guardado: {len(cruce_final):,} registros")

    # ----------------------------------------------------------
    # 5. TABLAS RESUMEN
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"5. TABLAS RESUMEN - {anio}")
    print("=" * 60)

    # Solo matcheados validos para resumenes
    validos = cruce[cruce['tiene_velocidad'] == True].copy()

    # 5.1 Resumen velocidad promedio por hora
    res_vel_hora = vel_horario.groupby('hora').agg(
        vel_promedio=('vel_promedio_hora', 'mean'),
        vel_mediana=('vel_promedio_hora', 'median'),
        vel_std=('vel_promedio_hora', 'std'),
    ).reset_index()
    res_vel_hora.to_csv(TABLES / "resumen_velocidad_por_hora.csv", index=False)

    # 5.2 Resumen accidentes por hora
    res_acc_hora = siniestralidad.groupby('Hora_Acc').size().reset_index(name='num_accidentes')
    res_acc_hora.to_csv(TABLES / "resumen_accidentes_por_hora.csv", index=False)

    # 5.3 Tabla cruzada hora: accidentes + velocidad
    res_cruce_hora = res_acc_hora.merge(res_vel_hora, left_on='Hora_Acc', right_on='hora', how='outer')
    res_cruce_hora = res_cruce_hora.drop(columns=['hora'], errors='ignore').sort_values('Hora_Acc')
    res_cruce_hora.to_csv(TABLES / "resumen_cruce_hora.csv", index=False)

    # 5.4 Velocidad por gravedad de accidente
    if len(validos) > 0:
        res_grav = validos.groupby('Gravedad_Indicador_Tradicional').agg(
            vel_promedio=('vel_promedio_hora', 'mean'),
            vel_mediana=('vel_promedio_hora', 'median'),
            num_accidentes=('vel_promedio_hora', 'count'),
        ).reset_index()
        res_grav.to_csv(TABLES / "resumen_cruce_gravedad.csv", index=False)

    # 5.5 Cobertura del cruce
    dist_match = sini_con_coords.loc[sini_con_coords['match_valido'], 'distancia_metros_aprox']
    cobertura = pd.DataFrame({
        'metrica': [
            'Total accidentes', 'Sin coordenadas', 'Con coordenadas',
            'Match <=500m', 'Match >500m (descartados)', 'Con velocidad asignada',
            'Distancia promedio (m)', 'Distancia mediana (m)', 'Distancia max (m)',
        ],
        'valor': [
            len(siniestralidad), sin_coords.sum(), len(sini_con_coords),
            matcheados, no_matcheados, con_vel,
            dist_match.mean() if len(dist_match) > 0 else 0,
            dist_match.median() if len(dist_match) > 0 else 0,
            dist_match.max() if len(dist_match) > 0 else 0,
        ]
    })
    cobertura.to_csv(TABLES / "resumen_cobertura_cruce.csv", index=False)
    print(f"   [OK] Tablas resumen {anio} guardadas")

    # ----------------------------------------------------------
    # 6. VISUALIZACIONES
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"6. VISUALIZACIONES - {anio}")
    print("=" * 60)

    sns.set_style("whitegrid")

    # 6.1 Velocidad vs Accidentes por hora (dual axis)
    fig, ax1 = plt.subplots(figsize=(14, 7))
    color1 = '#e74c3c'
    color2 = '#3498db'

    ax1.bar(res_cruce_hora['Hora_Acc'], res_cruce_hora['num_accidentes'],
            color=color1, alpha=0.6, label='Accidentes', zorder=2)
    ax1.set_xlabel('Hora del dia')
    ax1.set_ylabel('Numero de accidentes', color=color1)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xticks(range(24))

    ax2 = ax1.twinx()
    ax2.plot(res_cruce_hora['Hora_Acc'], res_cruce_hora['vel_promedio'],
             color=color2, linewidth=2.5, marker='o', markersize=6, label='Vel. promedio', zorder=3)
    ax2.fill_between(res_cruce_hora['Hora_Acc'],
                     res_cruce_hora['vel_promedio'] - res_cruce_hora['vel_std'],
                     res_cruce_hora['vel_promedio'] + res_cruce_hora['vel_std'],
                     alpha=0.15, color=color2)
    ax2.set_ylabel('Velocidad promedio (km/h)', color=color2)
    ax2.tick_params(axis='y', labelcolor=color2)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=11)

    plt.title(f'Accidentes vs Velocidad Promedio por Hora del Dia - Bogota, Octubre {anio}')
    plt.tight_layout()
    plt.savefig(FIGURES / "vel_vs_accidentes_por_hora.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("   [OK] vel_vs_accidentes_por_hora.png")

    # 6.2 Distribucion de distancias del cruce
    fig, ax = plt.subplots(figsize=(12, 6))
    if len(dist_match) > 0:
        ax.hist(dist_match, bins=50, color='#2ecc71', edgecolor='white', alpha=0.8)
        ax.axvline(dist_match.median(), color='#e74c3c', linestyle='--', linewidth=2,
                   label=f'Mediana: {dist_match.median():.0f}m')
    ax.set_xlabel('Distancia al corredor mas cercano (metros)')
    ax.set_ylabel('Numero de accidentes')
    ax.set_title(f'Distribucion de Distancias - Accidentes a Corredor Vial Mas Cercano ({anio})')
    ax.legend(fontsize=11)
    plt.tight_layout()
    plt.savefig(FIGURES / "distribucion_distancias_cruce.png", dpi=150, bbox_inches='tight')
    plt.close()
    print("   [OK] distribucion_distancias_cruce.png")

    # 6.3 Velocidad por gravedad (boxplot)
    if len(validos) > 0:
        fig, ax = plt.subplots(figsize=(12, 7))
        order = validos.groupby('Gravedad_Indicador_Tradicional')['vel_promedio_hora'].median().sort_values().index
        sns.boxplot(data=validos, x='Gravedad_Indicador_Tradicional', y='vel_promedio_hora',
                    order=order, palette='RdYlGn_r', ax=ax)
        ax.set_xlabel('Gravedad del Accidente')
        ax.set_ylabel('Velocidad Promedio en Corredor (km/h)')
        ax.set_title(f'Velocidad Promedio del Corredor segun Gravedad del Accidente ({anio})')
        plt.xticks(rotation=15)
        plt.tight_layout()
        plt.savefig(FIGURES / "vel_promedio_por_gravedad.png", dpi=150, bbox_inches='tight')
        plt.close()
        print("   [OK] vel_promedio_por_gravedad.png")

    # 6.4 Heatmap hora x corredor (top 20 corredores con mas accidentes)
    if len(validos) > 0:
        top_tids = validos['TID_cercano'].value_counts().head(20).index
        hm_data = validos[validos['TID_cercano'].isin(top_tids)].copy()
        hm_data['corredor'] = hm_data['corredor_from'] + ' -> ' + hm_data['corredor_to']

        pivot = hm_data.pivot_table(index='corredor', columns='Hora_Acc',
                                    values='vel_promedio_hora', aggfunc='mean')
        fig, ax = plt.subplots(figsize=(16, 10))
        sns.heatmap(pivot, cmap='RdYlGn', annot=True, fmt='.0f', linewidths=0.5,
                    ax=ax, cbar_kws={'label': 'Vel. Promedio (km/h)'})
        ax.set_title(f'Velocidad Promedio por Hora - Top 20 Corredores con Mas Accidentes ({anio})')
        ax.set_xlabel('Hora del dia')
        ax.set_ylabel('Corredor vial')
        plt.tight_layout()
        plt.savefig(FIGURES / "mapa_calor_accidentes_velocidad.png", dpi=150, bbox_inches='tight')
        plt.close()
        print("   [OK] mapa_calor_accidentes_velocidad.png")

    # 6.5 Scatter: accidentes vs velocidad promedio por corredor
    if len(validos) > 0:
        por_corredor = validos.groupby('TID_cercano').agg(
            num_accidentes=('Codigo_Accidente', 'count'),
            vel_promedio=('vel_promedio_hora', 'mean'),
            corredor_from=('corredor_from', 'first'),
            corredor_to=('corredor_to', 'first'),
        ).reset_index()

        fig, ax = plt.subplots(figsize=(12, 7))
        scatter = ax.scatter(por_corredor['vel_promedio'], por_corredor['num_accidentes'],
                             s=por_corredor['num_accidentes'] * 5, alpha=0.6,
                             c=por_corredor['vel_promedio'], cmap='RdYlGn', edgecolors='gray')
        plt.colorbar(scatter, label='Vel. Promedio (km/h)')

        # Anotar top 5
        top5 = por_corredor.nlargest(5, 'num_accidentes')
        for _, row in top5.iterrows():
            ax.annotate(f"{row['corredor_from']}->{row['corredor_to']}",
                        (row['vel_promedio'], row['num_accidentes']),
                        fontsize=8, ha='left', va='bottom')

        ax.set_xlabel('Velocidad Promedio del Corredor (km/h)')
        ax.set_ylabel('Numero de Accidentes')
        ax.set_title(f'Relacion Velocidad Promedio vs Accidentes por Corredor Vial ({anio})')
        plt.tight_layout()
        plt.savefig(FIGURES / "scatter_vel_accidentes.png", dpi=150, bbox_inches='tight')
        plt.close()
        print("   [OK] scatter_vel_accidentes.png")

    # ----------------------------------------------------------
    # 7. REPORTE FINAL
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"7. REPORTE FINAL - {anio}")
    print("=" * 60)
    print(f"   Total accidentes:           {len(siniestralidad):,}")
    print(f"   Sin coordenadas:            {sin_coords.sum()}")
    print(f"   Matcheados (<=500m):        {matcheados}")
    print(f"   Con velocidad asignada:      {con_vel}")
    print(f"   Cobertura:                   {con_vel / len(siniestralidad) * 100:.1f}%")
    if len(dist_match) > 0:
        print(f"   Dist. promedio match:        {dist_match.mean():.0f}m")
        print(f"   Dist. mediana match:         {dist_match.median():.0f}m")
    print(f"\n   Archivos generados en:")
    print(f"      {PROCESSED}")
    print(f"      {TABLES}")
    print(f"      {FIGURES}")
    print(f"\n   [OK] Proceso {anio} completado exitosamente")


# ============================================================
# EJECUCION PRINCIPAL
# ============================================================
for config in ANIOS:
    procesar_cruce(config, siniestralidad_full)

print("\n" + "=" * 60)
print("PROCESO COMPLETO - Ambos anios procesados")
print("=" * 60)
