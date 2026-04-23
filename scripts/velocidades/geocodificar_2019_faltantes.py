# -*- coding: utf-8 -*-
"""
Geocodifica los TIDs del dataset 2019 que no están en segmentos_geocodificados.csv.
Actualiza el archivo de referencia y re-aplica la limpieza + filtro de coords al 2019.
"""
import sys, io, re, time, warnings
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

import requests
import pandas as pd
import numpy as np
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich import box
from rich.table import Table

console = Console()

DATA    = Path("data")
GEO_CSV = DATA / "segmentos_geocodificados.csv"
CSV_19  = DATA / "Velocidades_Bitcarrier_Octubre_2019_7909733598528545915.csv"
OUT_19_PQ  = DATA / "velocidades_2019_final.parquet"
OUT_19_CSV = DATA / "velocidades_2019_final.csv"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS       = {"User-Agent": "DataJam-Bogota-Geo2019/1.0"}
DELAY         = 1.1
BBOX          = "-74.35,4.45,-73.98,4.85"

EXPAND = {
    r"^KR(\d+\w*)$":       r"Carrera \1",
    r"^CL(\d+\w*)$":       r"Calle \1",
    r"^DIAG(\d+\w*)$":     r"Diagonal \1",
    r"^TV(\d+\w*)$":       r"Transversal \1",
    r"^AK(\d+)$":          r"Avenida Carrera \1",
    r"^AV\.BOYACA$":       "Avenida Boyaca",
    r"^AV\.CARACAS$":      "Avenida Caracas",
    r"^CARACAS$":          "Avenida Caracas",
    r"^AV\.AMERICAS$":     "Avenida de las Americas",
    r"^AV\.SUBA$":         "Avenida Suba",
    r"^AV\.CORDOBA$":      "Avenida Cordoba",
    r"^AV\.P\.MAYO$":      "Avenida Primero de Mayo",
    r"^AV\.VILLAVICENCIO$":"Avenida Villavicencio",
    r"^AV\.CL127$":        "Avenida Calle 127",
    r"^AV\.CL59SUR$":      "Avenida Calle 59 Sur",
    r"^AUTONORTE$":        "Autopista Norte",
    r"^NQS$":              "NQS Bogota",
    r"^AV\.DORADO$":       "Avenida El Dorado",
    r"^AV\.CIRCUNVALAR$":  "Avenida Circunvalar",
    r"^BOYACA$":           "Avenida Boyaca",
    r"^AV\.ROJAS$":        "Avenida Rojas",
}

def expandir(raw: str) -> str:
    name = str(raw).strip().upper().split(",")[0].split(";")[0].strip()
    name = name.replace(" ", "")
    for pat, rep in EXPAND.items():
        r = re.sub(pat, rep, name, flags=re.IGNORECASE)
        if r != name:
            return r
    return name.replace(".", " ").title()

def geocode(nombre: str) -> tuple | None:
    try:
        r = requests.get(
            NOMINATIM_URL,
            params={"q": f"{nombre}, Bogota, Colombia", "format": "json",
                    "limit": 1, "countrycodes": "co",
                    "viewbox": BBOX, "bounded": 1},
            headers=HEADERS, timeout=10
        )
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 1: Identificar TIDs faltantes
# ═══════════════════════════════════════════════════════════════════════════════

console.print(Panel.fit(
    "[bold magenta]Geocodificacion complementaria - 2019[/]\n"
    "[dim]Solo los TIDs de 2019 que no estan en la tabla de referencia[/]",
    border_style="bright_blue"
))

console.print("\n[bold yellow]Identificando TIDs faltantes...[/]")
df19 = pd.read_csv(CSV_19, low_memory=False)
geo  = pd.read_csv(GEO_CSV)

tids_faltantes = sorted(set(df19["TID"].unique()) - set(geo["TID"].unique()))
console.print(f"  TIDs en 2019:        {df19['TID'].nunique()}")
console.print(f"  TIDs ya geocodif.:   {geo['TID'].nunique()}")
console.print(f"  [yellow]TIDs que faltan:    {len(tids_faltantes)}[/]")

# Extraer atributos de esos TIDs desde el CSV 2019
segs = (
    df19[df19["TID"].isin(tids_faltantes)]
    .groupby("TID")
    .agg(NAME_FROM=("NAME_FROM","first"),
         NAME_TO=("NAME_TO","first"),
         DISTANCE_m=("DISTANCE","first"))
    .reset_index()
)

# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 2: Geocodificar los faltantes
# ═══════════════════════════════════════════════════════════════════════════════

console.print(f"\n[bold yellow]Geocodificando {len(segs)} segmentos "
              f"(aprox. {len(segs)*2*DELAY/60:.0f} min)...[/]")

nuevos = []
ok_count = 0

with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TextColumn("[bold]{task.completed}/{task.total}"),
    TimeRemainingColumn(),
    console=console, transient=False
) as progress:
    tarea = progress.add_task("Geocodificando...", total=len(segs))

    for row in segs.itertuples():
        # FROM
        q_from     = expandir(row.NAME_FROM)
        coord_from = geocode(q_from)
        time.sleep(DELAY)

        # TO (primer elemento)
        to_raw = str(row.NAME_TO).split(";")[0].split(",")[0].strip()
        q_to       = expandir(to_raw)
        coord_to   = geocode(q_to)
        time.sleep(DELAY)

        lat_from = coord_from[0] if coord_from else None
        lon_from = coord_from[1] if coord_from else None
        lat_to   = coord_to[0]   if coord_to   else None
        lon_to   = coord_to[1]   if coord_to   else None

        if lat_from and lat_to:
            lat_c, lon_c, conf = (lat_from+lat_to)/2, (lon_from+lon_to)/2, "alta"
        elif lat_from:
            lat_c, lon_c, conf = lat_from, lon_from, "media"
        elif lat_to:
            lat_c, lon_c, conf = lat_to, lon_to, "media"
        else:
            lat_c = lon_c = None
            conf  = "sin_coords"

        if lat_c:
            ok_count += 1

        nuevos.append({
            "TID": row.TID, "NAME_FROM": row.NAME_FROM, "NAME_TO": row.NAME_TO,
            "DISTANCE_m": row.DISTANCE_m,
            "VEL_MEDIA": None, "VEL_PICO": None, "N_REGISTROS": None,
            "lat_from": lat_from, "lon_from": lon_from,
            "lat_to": lat_to,   "lon_to": lon_to,
            "lat": lat_c, "lon": lon_c,
            "confianza": conf,
            "query_from": q_from, "query_to": q_to,
        })
        progress.advance(tarea)

df_nuevos = pd.DataFrame(nuevos)
console.print(f"\n  [green]OK[/] {ok_count}/{len(segs)} nuevos TIDs geocodificados "
              f"({ok_count/len(segs)*100:.1f}%)")

# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 3: Actualizar tabla de referencia
# ═══════════════════════════════════════════════════════════════════════════════

console.print("\n[bold yellow]Actualizando segmentos_geocodificados.csv...[/]")
geo_actualizado = pd.concat([geo, df_nuevos], ignore_index=True)
geo_actualizado.to_csv(GEO_CSV, index=False, encoding="utf-8")
console.print(f"  [green]OK[/] Total TIDs en tabla: {len(geo_actualizado)}")

# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 4: Re-aplicar limpieza al 2019 con la tabla completa
# ═══════════════════════════════════════════════════════════════════════════════

console.print("\n[bold yellow]Re-aplicando limpieza al dataset 2019...[/]")

FMT = "%m/%d/%Y %I:%M:%S %p"
ORDEN_DIAS = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"]
MAPA_DIA   = {0:"Lunes",1:"Martes",2:"Miercoles",3:"Jueves",
              4:"Viernes",5:"Sabado",6:"Domingo"}
COLS_DROP_19 = {"OBJECTID","CODIGO","TYPE","COEF_BRT","COEF_MIXTO",
                "VEL_MEDIA_BRT","VEL_MEDIA_MIXTO","VEL_MEDIA_PONDERADA","VEL_PONDERADA"}
COLS_REFINAR = ["Shape_Length","lat_from","lon_from","lat_to","lon_to"]

df = df19.copy()

# 1. Eliminar columnas basura
bad_col = [c for c in df.columns if c.upper() not in ("AÑO",) and
           len(c) <= 4 and "O" in c.upper() and "A" in c.upper()]
for c in bad_col:
    if c != "AÑO": df = df.rename(columns={c: "AÑO"})

cols_drop = [c for c in df.columns if c in COLS_DROP_19 or c == "AÑO"]
df = df.drop(columns=cols_drop, errors="ignore")

# 2. Fechas
df["INICIO"] = pd.to_datetime(df["INICIO"], format=FMT, errors="coerce")
df["FIN"]    = pd.to_datetime(df["FIN"],    format=FMT, errors="coerce")
df = df.dropna(subset=["INICIO","FIN"])

# 3. Columnas derivadas
df["ANIO"]        = df["INICIO"].dt.year.astype("int16")
df["DIA_SEMANA"]  = df["INICIO"].dt.dayofweek.map(MAPA_DIA)
df["CUARTO_HORA"] = df["INICIO"].dt.strftime("%H:%M")

# 4. Texto
for c in ["NAME_FROM","NAME_TO","MES"]:
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip().str.upper().replace("NAN", pd.NA)

# 5. Filtros de calidad
before = len(df)
df = df.drop_duplicates(subset=["TID","INICIO","FIN"], keep="first")
df = df[df["VEL_PROMEDIO"] <= 150]
df = df.rename(columns={"DISTANCE": "DISTANCE_M", "Shape__Length": "Shape_Length"})
df["DISTANCE_M"] = df["DISTANCE_M"].fillna(0).astype(int)

# 6. Columnas faltantes comunes
if "NUMDISPOSITIVOS" not in df.columns: df["NUMDISPOSITIVOS"] = pd.NA
if "VEL_PONDERADA"  not in df.columns: df["VEL_PONDERADA"]   = pd.NA

# 7. JOIN con tabla geocodificada actualizada
geo_ok = geo_actualizado[["TID","lat","lon","lat_from","lon_from",
                           "lat_to","lon_to","confianza"]].rename(
    columns={"confianza":"confianza_geo"})
df = df.merge(geo_ok, on="TID", how="left")

# 8. Eliminar columnas redundantes (refinar)
df = df.drop(columns=[c for c in COLS_REFINAR if c in df.columns], errors="ignore")

# 9. Filtrar fuera de bbox
mask_ok = (
    df["lat"].notna() &
    df["lon"].notna() &
    df["lat"].between(4.4, 4.9) &
    df["lon"].between(-74.4, -73.9)
)
total = len(df)
df = df[mask_ok].reset_index(drop=True)

# 10. Seleccionar columnas canonicas
COLS_FINAL = ["TID","ANIO","INICIO","FIN","CUARTO_HORA","DIA_SEMANA","MES",
              "NAME_FROM","NAME_TO","DISTANCE_M","VEL_PROMEDIO","VEL_PONDERADA",
              "NUMDISPOSITIVOS","lat","lon","confianza_geo"]
cols_ok = [c for c in COLS_FINAL if c in df.columns]
df = df[cols_ok]

# 11. Tipos
df["TID"]  = df["TID"].astype("int32")
df["ANIO"] = df["ANIO"].astype("int16")
if "HORA" in df.columns:
    df["HORA"] = df["HORA"].astype("int8")
df["DIA_SEMANA"] = pd.Categorical(df["DIA_SEMANA"], categories=ORDEN_DIAS, ordered=True)

console.print(f"  [green]OK[/] Filas limpias: {len(df):,} / {len(df19):,} originales")
console.print(f"  Con lat/lon: {df['lat'].notna().sum():,} ({df['lat'].notna().sum()/len(df)*100:.1f}%)")

# Distribucion confianza
console.print("  Confianza_geo:")
for v, c in df["confianza_geo"].value_counts().items():
    console.print(f"    {v:<15} {c:>10,}  ({c/len(df)*100:.1f}%)")

# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 5: Guardar resultado final
# ═══════════════════════════════════════════════════════════════════════════════

console.print("\n[bold yellow]Guardando dataset 2019 final actualizado...[/]")
df.to_parquet(OUT_19_PQ,  index=False, engine="pyarrow")
df.to_csv(OUT_19_CSV,     index=False, encoding="utf-8")
console.print(f"  [green]OK[/] {OUT_19_PQ}   ({OUT_19_PQ.stat().st_size/1024/1024:.1f} MB)")
console.print(f"  [green]OK[/] {OUT_19_CSV}  ({OUT_19_CSV.stat().st_size/1024/1024:.1f} MB)")

# Resumen comparativo
t = Table(box=box.ROUNDED, show_lines=True)
t.add_column("Concepto",           style="bold white")
t.add_column("Valor",              style="yellow", justify="right")
t.add_row("Total original 2019",   f"{len(df19):,}")
t.add_row("TIDs nuevamente geo.",  f"{ok_count}")
t.add_row("Filas finales",         f"{len(df):,}")
t.add_row("Filas con lat/lon",     f"{df['lat'].notna().sum():,}")
t.add_row("Cobertura (%)",         f"{df['lat'].notna().sum()/len(df)*100:.1f}%")
t.add_row("Archivos actualizados", "2")
console.print(t)

console.print(Panel.fit(
    "[bold green]Proceso completo![/]\n"
    "[dim]El dataset 2019 ahora tiene cobertura maxima de coordenadas.[/]\n"
    "[dim]Listo para JOIN con camaras y accidentes.[/]",
    border_style="green"
))
