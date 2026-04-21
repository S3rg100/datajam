import geopandas as gpd
import pandas as pd
from pathlib import Path

# ==========================================
# 1. RUTAS
# ==========================================
BASE_DIR = Path(__file__).resolve().parents[1]
CARPETA_RECURSOS = BASE_DIR / "data" / "raw_data" / "camaras_salvavidas"
ARCHIVO_SHP = CARPETA_RECURSOS / "Camaras_Salvavidas_Bogota.shp"

print("BASE_DIR:", BASE_DIR)
print("CARPETA_RECURSOS:", CARPETA_RECURSOS)
print("ARCHIVO_SHP:", ARCHIVO_SHP)
print("¿Existe carpeta de datos fuente?:", CARPETA_RECURSOS.exists())
print("¿Existe shapefile?:", ARCHIVO_SHP.exists())

if not CARPETA_RECURSOS.exists():
    raise FileNotFoundError(
        "No existe la carpeta 'data/raw_data/camaras_salvavidas' en el repositorio."
    )

if not ARCHIVO_SHP.exists():
    raise FileNotFoundError(
        "No existe el archivo 'Camaras_Salvavidas_Bogota.shp' dentro de 'data/raw_data/camaras_salvavidas'."
    )

# ==========================================
# 2. LEER SHAPEFILE
# ==========================================
gdf = gpd.read_file(ARCHIVO_SHP)

print("\nShapefile cargado correctamente")
print(f"Registros: {len(gdf)}")
print(f"Columnas: {len(gdf.columns)}")

print("\nColumnas encontradas:")
print(list(gdf.columns))

print("\nCRS original:")
print(gdf.crs)

# ==========================================
# 3. VALIDAR CRS Y TRANSFORMAR A WGS84
# ==========================================
if gdf.crs is None:
    raise ValueError("El shapefile no tiene sistema de coordenadas definido.")

gdf_wgs84 = gdf.to_crs(epsg=4326)

# ==========================================
# 4. EXTRAER COORDENADAS
# ==========================================
gdf_wgs84["longitud"] = gdf_wgs84.geometry.x
gdf_wgs84["latitud"] = gdf_wgs84.geometry.y

# ==========================================
# 5. CREAR TABLA BASE
# ==========================================
df_camaras = pd.DataFrame(gdf_wgs84.drop(columns="geometry"))

# Agregar identificador técnico
df_camaras.insert(0, "id_registro", range(1, len(df_camaras) + 1))

# ==========================================
# 6. INSPECCIÓN INICIAL
# ==========================================
print("\nPrimeras filas:")
print(df_camaras.head())

print("\nTipos de dato:")
print(df_camaras.dtypes)

print("\nNulos por columna:")
print(df_camaras.isna().sum())

print("\nDuplicados exactos:")
print(df_camaras.duplicated().sum())

# ==========================================
# 7. EXPORTAR RESULTADOS
# ==========================================
CARPETA_SALIDA = BASE_DIR / "data" / "processed_data" / "camaras_salvavidas"
CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

ARCHIVO_CSV = CARPETA_SALIDA / "tabla_camaras_salvavidas_raw.csv"
ARCHIVO_XLSX = CARPETA_SALIDA / "tabla_camaras_salvavidas_raw.xlsx"
ARCHIVO_GEOJSON = CARPETA_SALIDA / "camaras_salvavidas_raw.geojson"

df_camaras.to_csv(ARCHIVO_CSV, index=False, encoding="utf-8-sig")
df_camaras.to_excel(ARCHIVO_XLSX, index=False)
gdf_wgs84.to_file(ARCHIVO_GEOJSON, driver="GeoJSON")

print("\nArchivos exportados correctamente:")
print(ARCHIVO_CSV)
print(ARCHIVO_XLSX)
print(ARCHIVO_GEOJSON)