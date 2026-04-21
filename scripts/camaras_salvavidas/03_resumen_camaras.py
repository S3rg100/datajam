import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ==========================================
# 1. RUTAS
# ==========================================
BASE_DIR = Path(__file__).resolve().parents[1]

CARPETA_LIMPIEZA = BASE_DIR / "data" / "cleaned_data" / "camaras_salvavidas"

CARPETA_TABLAS = BASE_DIR / "outputs" / "tables" / "camaras_salvavidas"
CARPETA_FIGURAS = BASE_DIR / "outputs" / "figures" / "camaras_salvavidas"

CARPETA_RESUMEN_GENERAL = CARPETA_TABLAS / "01_resumen_general"
CARPETA_FRECUENCIAS = CARPETA_TABLAS / "02_frecuencias"
CARPETA_CRUCES = CARPETA_TABLAS / "03_cruces"
CARPETA_GRAFICOS_FRECUENCIAS = CARPETA_FIGURAS / "frecuencias"
CARPETA_GRAFICOS_CRUCES = CARPETA_FIGURAS / "cruces"

for carpeta in [
    CARPETA_RESUMEN_GENERAL,
    CARPETA_FRECUENCIAS,
    CARPETA_CRUCES,
    CARPETA_GRAFICOS_FRECUENCIAS,
    CARPETA_GRAFICOS_CRUCES,
]:
    carpeta.mkdir(parents=True, exist_ok=True)

ARCHIVO_CLEAN = CARPETA_LIMPIEZA / "tabla_camaras_salvavidas_clean.csv"

if not ARCHIVO_CLEAN.exists():
    raise FileNotFoundError(f"No se encontró el archivo limpio en: {ARCHIVO_CLEAN}")

# ==========================================
# 2. LEER TABLA LIMPIA
# ==========================================
df = pd.read_csv(ARCHIVO_CLEAN, encoding="utf-8-sig")

print("Archivo cargado correctamente")
print(f"Registros: {len(df)}")
print(f"Columnas: {len(df.columns)}")

# ==========================================
# 3. FUNCIONES AUXILIARES
# ==========================================
def resumen_frecuencias(dataframe, columna, nombre_salida):
    resumen = dataframe[columna].value_counts(dropna=False).reset_index()
    resumen.columns = [columna, "conteo"]
    resumen["porcentaje"] = (resumen["conteo"] / len(dataframe) * 100).round(2)

    resumen.to_csv(
        CARPETA_FRECUENCIAS / f"{nombre_salida}.csv",
        index=False,
        encoding="utf-8-sig"
    )
    resumen.to_excel(
        CARPETA_FRECUENCIAS / f"{nombre_salida}.xlsx",
        index=False
    )
    return resumen

def grafico_barras_con_etiquetas(
    resumen,
    columna_x,
    columna_y,
    titulo,
    nombre_archivo,
    rotacion=45,
    top_n=None,
    horizontal=False
):
    data = resumen.copy()

    if top_n is not None:
        data = data.head(top_n)

    plt.figure(figsize=(12, 7))

    if horizontal:
        barras = plt.barh(data[columna_x].astype(str), data[columna_y])
        plt.xlabel("Conteo")
        plt.ylabel(columna_x)
        plt.title(titulo)

        for barra in barras:
            ancho = barra.get_width()
            y = barra.get_y() + barra.get_height() / 2
            plt.text(ancho + 0.2, y, f"{int(ancho)}", va="center")
    else:
        barras = plt.bar(data[columna_x].astype(str), data[columna_y])
        plt.xlabel(columna_x)
        plt.ylabel("Conteo")
        plt.title(titulo)
        plt.xticks(rotation=rotacion, ha="right")

        for barra in barras:
            altura = barra.get_height()
            plt.text(
                barra.get_x() + barra.get_width() / 2,
                altura + 0.2,
                f"{int(altura)}",
                ha="center",
                va="bottom"
            )

    plt.tight_layout()
    plt.savefig(CARPETA_GRAFICOS_FRECUENCIAS / nombre_archivo, dpi=300, bbox_inches="tight")
    plt.close()

def guardar_cruce_y_heatmap(filas, columnas, nombre_base, titulo):
    tabla = pd.crosstab(df[filas], df[columnas])

    tabla.to_csv(
        CARPETA_CRUCES / f"{nombre_base}.csv",
        encoding="utf-8-sig"
    )
    tabla.reset_index().to_excel(
        CARPETA_CRUCES / f"{nombre_base}.xlsx",
        index=False
    )

    fig, ax = plt.subplots(figsize=(max(10, len(tabla.columns) * 1.3), max(8, len(tabla.index) * 0.6)))
    im = ax.imshow(tabla.values, aspect="auto")

    ax.set_xticks(range(len(tabla.columns)))
    ax.set_yticks(range(len(tabla.index)))
    ax.set_xticklabels(tabla.columns, rotation=45, ha="right")
    ax.set_yticklabels(tabla.index)

    ax.set_title(titulo)
    ax.set_xlabel(columnas)
    ax.set_ylabel(filas)

    for i in range(tabla.shape[0]):
        for j in range(tabla.shape[1]):
            valor = tabla.iloc[i, j]
            ax.text(j, i, str(valor), ha="center", va="center")

    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    plt.savefig(
        CARPETA_GRAFICOS_CRUCES / f"grafico_{nombre_base}.png",
        dpi=300,
        bbox_inches="tight"
    )
    plt.close()

    return tabla

# ==========================================
# 4. TABLAS RESUMEN
# ==========================================
res_localidad = resumen_frecuencias(df, "localidad", "resumen_camaras_por_localidad")
res_corredor = resumen_frecuencias(df, "corredor_principal", "resumen_camaras_por_corredor")
res_velocidad = resumen_frecuencias(df, "velocidad_maxima", "resumen_camaras_por_velocidad")
res_infraccion = resumen_frecuencias(df, "infraccion", "resumen_camaras_por_infraccion")
res_calzada = resumen_frecuencias(df, "calzada", "resumen_camaras_por_calzada")
res_sentido = resumen_frecuencias(df, "sentido", "resumen_camaras_por_sentido")
res_numero_acto = resumen_frecuencias(df, "numero_acto", "resumen_camaras_por_numero_acto")

# ==========================================
# 5. GRÁFICOS DE FRECUENCIAS
# ==========================================
grafico_barras_con_etiquetas(
    res_localidad, "localidad", "conteo",
    "Número de cámaras por localidad",
    "grafico_camaras_por_localidad.png"
)

grafico_barras_con_etiquetas(
    res_velocidad, "velocidad_maxima", "conteo",
    "Número de cámaras por velocidad máxima",
    "grafico_camaras_por_velocidad.png",
    rotacion=0
)

grafico_barras_con_etiquetas(
    res_corredor, "corredor_principal", "conteo",
    "Top 10 corredores con más cámaras",
    "grafico_top10_corredores.png",
    top_n=10
)

grafico_barras_con_etiquetas(
    res_infraccion, "infraccion", "conteo",
    "Número de cámaras por tipo de infracción",
    "grafico_camaras_por_infraccion.png"
)

grafico_barras_con_etiquetas(
    res_calzada, "calzada", "conteo",
    "Número de cámaras por tipo de calzada",
    "grafico_camaras_por_calzada.png",
    rotacion=0
)

grafico_barras_con_etiquetas(
    res_sentido, "sentido", "conteo",
    "Número de cámaras por sentido vial",
    "grafico_camaras_por_sentido.png"
)

grafico_barras_con_etiquetas(
    res_numero_acto, "numero_acto", "conteo",
    "Número de cámaras por acto administrativo",
    "grafico_camaras_por_numero_acto.png"
)

# ==========================================
# 6. CRUCES
# ==========================================
cruce_localidad_velocidad = guardar_cruce_y_heatmap(
    "localidad", "velocidad_maxima",
    "cruce_localidad_velocidad",
    "Cruce: Localidad vs Velocidad máxima"
)

cruce_localidad_infraccion = guardar_cruce_y_heatmap(
    "localidad", "infraccion",
    "cruce_localidad_infraccion",
    "Cruce: Localidad vs Infracción"
)

cruce_localidad_calzada = guardar_cruce_y_heatmap(
    "localidad", "calzada",
    "cruce_localidad_calzada",
    "Cruce: Localidad vs Calzada"
)

cruce_localidad_sentido = guardar_cruce_y_heatmap(
    "localidad", "sentido",
    "cruce_localidad_sentido",
    "Cruce: Localidad vs Sentido"
)

# ==========================================
# 7. RESUMEN GENERAL
# ==========================================
resumen_general = pd.DataFrame({
    "indicador": [
        "total_registros",
        "total_localidades",
        "total_corredores",
        "total_vias_secundarias",
        "total_velocidades",
        "total_infracciones",
        "total_calzadas",
        "total_sentidos",
        "total_actos_administrativos"
    ],
    "valor": [
        len(df),
        df["localidad"].nunique(dropna=True),
        df["corredor_principal"].nunique(dropna=True),
        df["via_secundaria"].nunique(dropna=True),
        df["velocidad_maxima"].nunique(dropna=True),
        df["infraccion"].nunique(dropna=True),
        df["calzada"].nunique(dropna=True),
        df["sentido"].nunique(dropna=True),
        df["numero_acto"].nunique(dropna=True)
    ]
})

resumen_general.to_csv(
    CARPETA_RESUMEN_GENERAL / "resumen_general_camaras.csv",
    index=False,
    encoding="utf-8-sig"
)
resumen_general.to_excel(
    CARPETA_RESUMEN_GENERAL / "resumen_general_camaras.xlsx",
    index=False
)

# ==========================================
# 8. CONSOLA
# ==========================================
print("\n================ RESUMEN GENERAL ================")
print(resumen_general)
print("\nTop 5 localidades con más cámaras:")
print(res_localidad.head())
print("\nArchivos generados en tablas:")
print(CARPETA_TABLAS)
print("\nArchivos generados en figuras:")
print(CARPETA_FIGURAS)