# -*- coding: utf-8 -*-
"""
=============================================================================
  LIMPIEZA DE SINIESTRALIDAD VIAL - Bogotá D.C.
=============================================================================
  Limpia y prepara el dataset crudo de siniestralidad de la Secretaría
  Distrital de Movilidad para su uso en el análisis comparativo.

  ENTRADA:
    data/raw_data/Siniestralidad/DataJamSiniestralidad.csv
      Dataset original con ~150K registros de accidentes viales (todos los años).

  SALIDA:
    data/cleaned_data/Siniestralidad/siniestralidad_clean.csv
      Dataset filtrado y limpio con ~4,334 registros (solo octubre 2019 y 2022).

  TRANSFORMACIONES APLICADAS:
    1. Columnas Con_* (booleanas): "SI" → 1, NaN → 0 (codificación binaria).
    2. Valores nulos en columnas de texto: rellenados con "N/A".
    3. Filtro temporal: solo registros de octubre 2019 y octubre 2022.
    4. Eliminación de columnas innecesarias: Formulario, Gravedad_indicador_30d,
       Fecha_Acc (redundante con AA_Acc y MM_Acc).
    5. Normalización de texto: Localidad, Gravedad y Tipo_Objeto_Fijo a formato
       Title Case para uniformidad.
=============================================================================
"""
import pandas as pd
from pathlib import Path

# ==========================================
# 1. RUTAS
# ==========================================
BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_RAW = BASE_DIR / "data" / "raw_data" / "Siniestralidad"
CARPETA_CLEAN = BASE_DIR / "data" / "cleaned_data" / "Siniestralidad"

CARPETA_CLEAN.mkdir(parents=True, exist_ok=True)

ARCHIVO_RAW = CARPETA_RAW / "DataJamSiniestralidad.csv"

if not ARCHIVO_RAW.exists():
    raise FileNotFoundError(f"No se encontró el archivo en: {ARCHIVO_RAW}")

# ==========================================
#  CARGAR DATOS
# ==========================================
df = pd.read_csv(ARCHIVO_RAW, low_memory=False)
print(f"Archivo cargado: {len(df)} registros")

#  Columnas Con_* → 0 y 1
cols_con = [col for col in df.columns if col.startswith("Con_")]
df[cols_con] = df[cols_con].apply(lambda col: col.map({"SI": 1}).fillna(0).astype(int))

#  Rellenar nulos con "N/A" (excepto Con_*)
cols_fillna = [col for col in df.columns if not col.startswith("Con_")]
df[cols_fillna] = df[cols_fillna].fillna("N/A")

#  Filtrar octubre 2019 y octubre 2022
df = df[(df["MM_Acc"].isin(["Octubre"])) & (df["AA_Acc"].isin([2019, 2022]))]

#  Eliminar columnas innecesarias
df = df.drop(columns=["Formulario", "Gravedad_indicador_30d", "Fecha_Acc"])

# Normalizar texto
df["Localidad"] = df["Localidad"].str.title()
df["Gravedad_Indicador_Tradicional"] = df["Gravedad_Indicador_Tradicional"].str.title()
df["Tipo_Objeto_Fijo"] = df["Tipo_Objeto_Fijo"].apply(lambda x: "N/A" if x == "N/A" else str(x).title())

# ==========================================
# 8. GUARDAR CSV LIMPIO
# ==========================================
ARCHIVO_CLEAN = CARPETA_CLEAN / "siniestralidad_clean.csv"
df.to_csv(ARCHIVO_CLEAN, index=False, encoding="utf-8-sig")
print(f"✅ CSV guardado en: {ARCHIVO_CLEAN}")
print(df.head(5))
print(df.shape)
