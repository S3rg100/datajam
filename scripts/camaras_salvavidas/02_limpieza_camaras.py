# -*- coding: utf-8 -*-
"""
=============================================================================
  LIMPIEZA DE CÁMARAS SALVAVIDAS - Bogotá D.C.
=============================================================================
  Limpia y normaliza la tabla de cámaras salvavidas generada en el paso 01.

  ENTRADA:
    data/raw_data/camaras_salvavidas/Camaras_Salvavidas_Bogota.shp

  SALIDAS:
    data/cleaned_data/camaras_salvavidas/tabla_camaras_salvavidas_clean.csv
    data/cleaned_data/camaras_salvavidas/tabla_camaras_salvavidas_clean.xlsx
    data/cleaned_data/camaras_salvavidas/camaras_salvavidas_clean.geojson
    data/cleaned_data/camaras_salvavidas/perfil_calidad_camaras.csv

  TRANSFORMACIONES APLICADAS:
    1. Reproyección de coordenadas a WGS84 (EPSG:4326).
    2. Normalización de nombres de columnas (minúsculas, sin tildes, snake_case).
    3. Limpieza de valores de texto (espacios, caracteres especiales).
    4. Renombre de columnas a nombres descriptivos en español.
    5. Conversión de campos numéricos (velocidad_maxima, carriles).
    6. Generación de perfil de calidad de datos por columna.
    7. Validación de geometrías y detección de duplicados.
=============================================================================
"""
import geopandas as gpd
import pandas as pd
import unicodedata
import re
from pathlib import Path

# ==========================================
# 1. RUTAS
# ==========================================
BASE_DIR = Path(__file__).resolve().parents[1]
CARPETA_RECURSOS = BASE_DIR / "data" / "raw_data" / "camaras_salvavidas"
CARPETA_SALIDA = BASE_DIR / "data" / "cleaned_data" / "camaras_salvavidas"
CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

ARCHIVO_SHP = CARPETA_RECURSOS / "Camaras_Salvavidas_Bogota.shp"

# ==========================================
# 2. FUNCIONES AUXILIARES
# ==========================================
def normalizar_nombre_columna(texto):
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto

def limpiar_texto(valor):
    if pd.isna(valor):
        return valor
    valor = str(valor).strip()
    valor = re.sub(r"\s+", " ", valor)
    return valor

def a_numerico(serie):
    return pd.to_numeric(
        serie.astype(str).str.replace(",", ".", regex=False).str.strip(),
        errors="coerce"
    )

# ==========================================
# 3. CARGAR SHAPEFILE
# ==========================================
print("Cargando shapefile...")
gdf = gpd.read_file(ARCHIVO_SHP)

print(f"Registros originales: {len(gdf)}")
print(f"CRS original: {gdf.crs}")

if gdf.crs is None:
    raise ValueError("El shapefile no tiene sistema de coordenadas definido.")

# Reproyectar para trabajar con coordenadas estándar
gdf = gdf.to_crs(epsg=4326)

# Extraer coordenadas desde la geometría
gdf["longitud_geom"] = gdf.geometry.x
gdf["latitud_geom"] = gdf.geometry.y

# ==========================================
# 4. NORMALIZAR NOMBRES DE COLUMNAS
# ==========================================
columnas_originales = list(gdf.columns)
gdf.columns = [normalizar_nombre_columna(col) for col in gdf.columns]

print("\nColumnas normalizadas:")
for original, nueva in zip(columnas_originales, gdf.columns):
    print(f"{original} -> {nueva}")

# ==========================================
# 5. LIMPIAR VALORES DE TEXTO
# ==========================================
columnas_texto = gdf.select_dtypes(include="object").columns.tolist()

for col in columnas_texto:
    gdf[col] = gdf[col].apply(limpiar_texto)

# ==========================================
# 6. RENOMBRAR COLUMNAS A NOMBRES MÁS CLAROS
# ==========================================
mapa_renombre = {
    "objectid_1": "objectid_fuente",
    "id_camara": "id_camara",
    "nombre_del": "nombre_camara",
    "direccion": "direccion",
    "numero_de": "numero_acto",
    "velocidadm": "velocidad_maxima",
    "corredor_p": "corredor_principal",
    "via_secund": "via_secundaria",
    "sentido": "sentido",
    "calzada": "calzada",
    "carriles": "carriles",
    "localidad": "localidad",
    "infraccion": "infraccion",
    "longitud": "longitud_fuente",
    "latitud": "latitud_fuente",
    "longitud_geom": "longitud",
    "latitud_geom": "latitud"
}

gdf = gdf.rename(columns=mapa_renombre)

# ==========================================
# 7. CONVERTIR CAMPOS NUMÉRICOS
# ==========================================
if "velocidad_maxima" in gdf.columns:
    gdf["velocidad_maxima"] = a_numerico(gdf["velocidad_maxima"])

if "carriles" in gdf.columns:
    gdf["carriles"] = a_numerico(gdf["carriles"])

# ==========================================
# 8. CREAR ID TÉCNICO
# ==========================================
gdf.insert(0, "id_registro", range(1, len(gdf) + 1))

# ==========================================
# 9. ORDENAR COLUMNAS
# ==========================================
columnas_preferidas = [
    "id_registro",
    "objectid_fuente",
    "id_camara",
    "nombre_camara",
    "direccion",
    "numero_acto",
    "velocidad_maxima",
    "corredor_principal",
    "via_secundaria",
    "sentido",
    "calzada",
    "carriles",
    "localidad",
    "infraccion",
    "longitud",
    "latitud",
    "longitud_fuente",
    "latitud_fuente",
    "geometry"
]

columnas_existentes = [col for col in columnas_preferidas if col in gdf.columns]
gdf = gdf[columnas_existentes]

# ==========================================
# 10. PERFIL DE CALIDAD
# ==========================================
perfil_calidad = pd.DataFrame({
    "columna": gdf.drop(columns="geometry").columns,
    "tipo_dato": [str(gdf[col].dtype) for col in gdf.drop(columns="geometry").columns],
    "nulos": [gdf[col].isna().sum() for col in gdf.drop(columns="geometry").columns],
    "no_nulos": [gdf[col].notna().sum() for col in gdf.drop(columns="geometry").columns],
    "valores_unicos": [gdf[col].nunique(dropna=True) for col in gdf.drop(columns="geometry").columns]
})

# Duplicados exactos
duplicados_exactos = gdf.drop(columns="geometry").duplicated().sum()

# Duplicados por id_camara
duplicados_id_camara = 0
if "id_camara" in gdf.columns:
    duplicados_id_camara = gdf["id_camara"].duplicated().sum()

# Geometrías nulas y válidas
geometrias_nulas = gdf.geometry.isna().sum()
geometrias_invalidas = (~gdf.geometry.is_valid).sum()

# ==========================================
# 11. EXPORTAR TABLA LIMPIA
# ==========================================
df_limpio = pd.DataFrame(gdf.drop(columns="geometry"))

ARCHIVO_CSV = CARPETA_SALIDA / "tabla_camaras_salvavidas_clean.csv"
ARCHIVO_XLSX = CARPETA_SALIDA / "tabla_camaras_salvavidas_clean.xlsx"
ARCHIVO_GEOJSON = CARPETA_SALIDA / "camaras_salvavidas_clean.geojson"
ARCHIVO_PERFIL = CARPETA_SALIDA / "perfil_calidad_camaras.csv"

df_limpio.to_csv(ARCHIVO_CSV, index=False, encoding="utf-8-sig")
df_limpio.to_excel(ARCHIVO_XLSX, index=False)
gdf.to_file(ARCHIVO_GEOJSON, driver="GeoJSON")
perfil_calidad.to_csv(ARCHIVO_PERFIL, index=False, encoding="utf-8-sig")

# ==========================================
# 12. RESUMEN EN CONSOLA
# ==========================================
print("\n================ RESUMEN DE LIMPIEZA ================")
print(f"Registros finales: {len(gdf)}")
print(f"Columnas finales: {len(gdf.columns)}")
print(f"Duplicados exactos: {duplicados_exactos}")
print(f"Duplicados por id_camara: {duplicados_id_camara}")
print(f"Geometrías nulas: {geometrias_nulas}")
print(f"Geometrías inválidas: {geometrias_invalidas}")

print("\nPrimeras filas de la tabla limpia:")
print(df_limpio.head())

print("\nTipos de dato finales:")
print(df_limpio.dtypes)

print("\nArchivos generados:")
print(ARCHIVO_CSV)
print(ARCHIVO_XLSX)
print(ARCHIVO_GEOJSON)
print(ARCHIVO_PERFIL)