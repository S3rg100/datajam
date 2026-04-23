# -*- coding: utf-8 -*-
"""
=============================================================================
  LIMPIEZA Y ENRIQUECIMIENTO - Velocidades Bitcarrier (2019 y 2022)
=============================================================================
  Aplica un pipeline de limpieza a ambos datasets y los enriquece con las
  coordenadas geocodificadas por segmento (TID).

  DECISIONES DE LIMPIEZA (documentadas):

  COLUMNAS ELIMINADAS (100% nulas en ambos años):
    - AÑO, LLAVE, COEF_BRT, COEF_MIXTO, VEL_MEDIA_BRT,
      VEL_MEDIA_MIXTO, VEL_MEDIA_PONDERADA  (2022)
    - CODIGO, COEF_BRT, COEF_MIXTO, VEL_MEDIA_BRT,
      VEL_MEDIA_MIXTO, VEL_MEDIA_PONDERADA, VEL_PONDERADA  (2019)
    - OBJECTID (ID de base de datos, sin valor analitico)
    - TYPE     (valor constante=1, sin variacion util)

  FILAS ELIMINADAS:
    - Segmentos sin NAME_FROM/NAME_TO (~3.2% en 2022, ninguno en 2019):
      son TIDs sin identificacion textual de tramo.
    - Velocidades fisicamente imposibles > 150 km/h (89 en 2022, 0 en 2019).
    - Duplicados exactos por clave TID + INICIO + FIN (700 en 2019).

  CORRECCIONES:
    - INICIO / FIN: parse a datetime estandar (UTC-5 Bogota implicito).
    - AÑO: se recupera desde la fecha INICIO (era 100% nulo en 2022).
    - DIA_SEMANA: se recalcula desde INICIO para garantizar consistencia.
    - CUARTO_HORA: se normaliza a HH:MM (algunos vienen con segundos).
    - NAME_FROM / NAME_TO: strip de espacios y uppercase.
    - DISTANCE: en 2019 ya era int; en 2022 era float => cast a int.

  ENRIQUECIMIENTO:
    - JOIN con segmentos_geocodificados.csv por TID:
        lat, lon           <- centroide del tramo
        lat_from, lon_from <- coords del extremo FROM
        lat_to,   lon_to   <- coords del extremo TO
        confianza_geo      <- alta / media / sin_coords
        query_from         <- nombre buscado en Nominatim (trazabilidad)

  COLUMNA NUEVA 'ANIO' (fuente INICIO):
    Necesaria para identificar el año al unir datasets.

  SALIDAS:
    data/velocidades_2022_clean.parquet
    data/velocidades_2019_clean.parquet
    data/velocidades_2022_clean.csv      (copia CSV si se necesita)
    data/velocidades_2019_clean.csv
    output/reporte_limpieza.html
=============================================================================
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import warnings, time
warnings.filterwarnings("ignore")

from pathlib import Path
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import jinja2

console = Console()

# ── Rutas ─────────────────────────────────────────────────────────────────────
DATA_DIR  = Path("data")
OUT_DIR   = Path("output")

CSV_2022  = DATA_DIR / "Velocidades_Bitcarrier_Octubre_2022_5740524589707522675.csv"
CSV_2019  = DATA_DIR / "Velocidades_Bitcarrier_Octubre_2019_7909733598528545915.csv"
GEO_CSV   = DATA_DIR / "segmentos_geocodificados.csv"

OUT_2022_PARQUET = DATA_DIR / "velocidades_2022_clean.parquet"
OUT_2019_PARQUET = DATA_DIR / "velocidades_2019_clean.parquet"
OUT_2022_CSV     = DATA_DIR / "velocidades_2022_clean.csv"
OUT_2019_CSV     = DATA_DIR / "velocidades_2019_clean.csv"

# ── Constantes ────────────────────────────────────────────────────────────────
VEL_MAX_FISICO   = 150.0   # km/h — limite fisico: se eliminan registros por encima
ORDEN_DIAS       = ["Lunes","Martes","Miercoles","Jueves","Viernes","Sabado","Domingo"]
FMT_FECHA        = "%m/%d/%Y %I:%M:%S %p"

# Columnas 100% nulas que se eliminan en cada año
COLS_ELIMINAR_22 = {
    "AÑO", "LLAVE", "COEF_BRT", "COEF_MIXTO",
    "VEL_MEDIA_BRT", "VEL_MEDIA_MIXTO", "VEL_MEDIA_PONDERADA",
    "OBJECTID", "TYPE",
}
COLS_ELIMINAR_19 = {
    "CODIGO", "COEF_BRT", "COEF_MIXTO",
    "VEL_MEDIA_BRT", "VEL_MEDIA_MIXTO", "VEL_MEDIA_PONDERADA", "VEL_PONDERADA",
    "OBJECTID", "TYPE", "AÑO",
}

# Columnas finales canonicas (orden y nombres uniformes para poder unir datasets)
COLS_FINAL = [
    "TID",
    "ANIO",
    "INICIO",
    "FIN",
    "HORA",
    "CUARTO_HORA",
    "DIA_SEMANA",
    "MES",
    "NAME_FROM",
    "NAME_TO",
    "DISTANCE_M",
    "VEL_PROMEDIO",
    "VEL_PONDERADA",
    "NUMDISPOSITIVOS",
    "Shape_Length",
    "lat",
    "lon",
    "lat_from",
    "lon_from",
    "lat_to",
    "lon_to",
    "confianza_geo",
]

# ═════════════════════════════════════════════════════════════════════════════
#  CLASE PIPELINE
# ═════════════════════════════════════════════════════════════════════════════

class PipelineLimpieza:
    """Pipeline de limpieza para un dataset de velocidades Bitcarrier."""

    def __init__(self, anio: int, csv_path: Path, geo: pd.DataFrame,
                 cols_eliminar: set):
        self.anio         = anio
        self.csv_path     = csv_path
        self.geo          = geo
        self.cols_eliminar = cols_eliminar
        self.log: list[dict] = []   # registro de cada paso
        self.df_orig: pd.DataFrame | None = None
        self.df: pd.DataFrame | None = None

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _registrar(self, paso: str, antes: int, despues: int, nota: str = ""):
        eliminados = antes - despues
        self.log.append({
            "paso":       paso,
            "antes":      antes,
            "despues":    despues,
            "eliminados": eliminados,
            "pct_elim":   round(eliminados / antes * 100, 3) if antes else 0,
            "nota":       nota,
        })
        simbolo = "[green]OK[/]" if eliminados == 0 else f"[yellow]-{eliminados:,}[/]"
        console.print(f"  {simbolo}  {paso}: {antes:,} -> {despues:,}  {nota}")

    # ── Pasos del pipeline ────────────────────────────────────────────────────

    def paso_cargar(self):
        console.print(f"\n  [dim]Leyendo {self.csv_path.name}...[/]")
        self.df = pd.read_csv(self.csv_path, low_memory=False)
        # Normalizar nombre de columna AÑO (puede llegar con caracter roto)
        bad_col = [c for c in self.df.columns if "O" in c.upper() and len(c) <= 4
                   and "A" in c.upper()]
        for c in bad_col:
            if c != "AÑO":
                self.df = self.df.rename(columns={c: "AÑO"})
        self.df_orig = self.df.copy()
        console.print(f"    Shape inicial: {self.df.shape}")

    def paso_eliminar_columnas(self):
        antes_cols = len(self.df.columns)
        cols_a_drop = [c for c in self.df.columns if c in self.cols_eliminar]
        self.df = self.df.drop(columns=cols_a_drop, errors="ignore")
        console.print(f"  [green]OK[/]  Columnas eliminadas ({len(cols_a_drop)}): {cols_a_drop}")

    def paso_parsear_fechas(self):
        antes = len(self.df)
        self.df["INICIO"] = pd.to_datetime(self.df["INICIO"], format=FMT_FECHA, errors="coerce")
        self.df["FIN"]    = pd.to_datetime(self.df["FIN"],    format=FMT_FECHA, errors="coerce")
        nulos_fecha = self.df["INICIO"].isna().sum()
        if nulos_fecha:
            self.df = self.df.dropna(subset=["INICIO", "FIN"])
            self._registrar("Fechas invalidas", antes, len(self.df),
                            f"({nulos_fecha} registros con fecha mal formada)")
        else:
            console.print(f"  [green]OK[/]  Fechas parseadas sin errores")

    def paso_anio_desde_fecha(self):
        """Recupera AÑO desde INICIO (en 2022 era 100% nulo)."""
        self.df["ANIO"] = self.df["INICIO"].dt.year
        console.print(f"  [green]OK[/]  ANIO derivado de INICIO: {sorted(self.df['ANIO'].unique())}")

    def paso_dia_semana(self):
        """Recalcula DIA_SEMANA desde INICIO para garantizar consistencia."""
        mapa_en_es = {0:"Lunes",1:"Martes",2:"Miercoles",3:"Jueves",
                      4:"Viernes",5:"Sabado",6:"Domingo"}
        self.df["DIA_SEMANA"] = self.df["INICIO"].dt.dayofweek.map(mapa_en_es)
        console.print(f"  [green]OK[/]  DIA_SEMANA recalculado desde INICIO")

    def paso_cuarto_hora(self):
        """Normaliza CUARTO_HORA a formato HH:MM."""
        self.df["CUARTO_HORA"] = self.df["INICIO"].dt.strftime("%H:%M")
        console.print(f"  [green]OK[/]  CUARTO_HORA normalizado a HH:MM ({self.df['CUARTO_HORA'].nunique()} franjas)")

    def paso_limpiar_texto(self):
        """Limpia NAME_FROM / NAME_TO: strip y uppercase."""
        for col in ["NAME_FROM", "NAME_TO", "MES"]:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(str).str.strip().str.upper()
                self.df[col] = self.df[col].replace("NAN", pd.NA)
        console.print(f"  [green]OK[/]  TEXT limpiado (NAME_FROM, NAME_TO, MES)")

    def paso_eliminar_sin_nombre(self):
        """Elimina registros sin NAME_FROM (sin referencia de tramo)."""
        antes = len(self.df)
        self.df = self.df.dropna(subset=["NAME_FROM"])
        self._registrar("Sin NAME_FROM (sin referencia de tramo)", antes, len(self.df))

    def paso_eliminar_velocidades_imposibles(self):
        """Elimina velocidades fisicamente imposibles (> 150 km/h en ciudad)."""
        antes = len(self.df)
        self.df = self.df[self.df["VEL_PROMEDIO"] <= VEL_MAX_FISICO]
        self._registrar(f"VEL_PROMEDIO > {VEL_MAX_FISICO} km/h (imposible)", antes, len(self.df))

    def paso_eliminar_duplicados(self):
        """Elimina duplicados por clave TID + INICIO + FIN."""
        antes = len(self.df)
        self.df = self.df.drop_duplicates(subset=["TID","INICIO","FIN"], keep="first")
        self._registrar("Duplicados TID+INICIO+FIN", antes, len(self.df))

    def paso_distancia(self):
        """Estandariza DISTANCE a entero y renombra a DISTANCE_M."""
        col_orig = "DISTANCE"
        if col_orig in self.df.columns:
            self.df["DISTANCE_M"] = self.df[col_orig].fillna(0).astype(int)
            self.df = self.df.drop(columns=[col_orig])
        console.print(f"  [green]OK[/]  DISTANCE -> DISTANCE_M (int, metros)")

    def paso_renombrar_shape(self):
        if "Shape__Length" in self.df.columns:
            self.df = self.df.rename(columns={"Shape__Length": "Shape_Length"})
        console.print(f"  [green]OK[/]  Shape__Length -> Shape_Length")

    def paso_numdispositivos(self):
        """En 2019 no existe NUMDISPOSITIVOS: crear con NaN."""
        if "NUMDISPOSITIVOS" not in self.df.columns:
            self.df["NUMDISPOSITIVOS"] = pd.NA
            console.print(f"  [yellow]!!  NUMDISPOSITIVOS no existe en {self.anio} -> columna con NaN[/]")
        else:
            console.print(f"  [green]OK[/]  NUMDISPOSITIVOS OK (min={self.df['NUMDISPOSITIVOS'].min()}, max={self.df['NUMDISPOSITIVOS'].max()})")

    def paso_vel_ponderada(self):
        """En 2019 VEL_PONDERADA es 100% nula (ya eliminada); crear columna vacía."""
        if "VEL_PONDERADA" not in self.df.columns:
            self.df["VEL_PONDERADA"] = pd.NA
            console.print(f"  [yellow]!!  VEL_PONDERADA no existe en {self.anio} -> columna con NaN[/]")

    def paso_geocodificar(self):
        """JOIN con tabla de segmentos geocodificados."""
        geo_cols = ["TID","lat","lon","lat_from","lon_from","lat_to","lon_to","confianza"]
        geo_sub  = self.geo[geo_cols].rename(columns={"confianza":"confianza_geo"})

        antes  = len(self.df)
        self.df = self.df.merge(geo_sub, on="TID", how="left")
        # Filtrar fuera de bounding box de Bogota
        fuera = (
            self.df["lat"].notna() &
            (~self.df["lat"].between(4.4, 4.9) | ~self.df["lon"].between(-74.4, -73.9))
        )
        self.df.loc[fuera, ["lat","lon","lat_from","lon_from","lat_to","lon_to"]] = np.nan
        self.df.loc[fuera, "confianza_geo"] = "fuera_bbox"

        con_coords = self.df["lat"].notna().sum()
        pct = con_coords / len(self.df) * 100
        console.print(f"  [green]OK[/]  JOIN geocodificado: {con_coords:,}/{len(self.df):,} filas con lat/lon  ({pct:.1f}%)")

    def paso_ordenar_columnas(self):
        """Reordena y selecciona columnas canonicas."""
        cols_disponibles = [c for c in COLS_FINAL if c in self.df.columns]
        cols_extra = [c for c in self.df.columns if c not in COLS_FINAL]
        self.df = self.df[cols_disponibles + cols_extra]
        console.print(f"  [green]OK[/]  Columnas reordenadas: {len(self.df.columns)} totales")

    def paso_tipos_finales(self):
        """Garantiza tipos de dato correctos."""
        cast_map = {
            "HORA":  "int8",
            "ANIO":  "int16",
            "TID":   "int32",
        }
        for col, dtype in cast_map.items():
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(dtype)
        if "DIA_SEMANA" in self.df.columns:
            self.df["DIA_SEMANA"] = pd.Categorical(
                self.df["DIA_SEMANA"], categories=ORDEN_DIAS, ordered=True
            )
        console.print(f"  [green]OK[/]  Tipos de dato optimizados")

    # ── Ejecucion completa ─────────────────────────────────────────────────────

    def ejecutar(self) -> pd.DataFrame:
        console.print(Panel.fit(
            f"[bold cyan]Pipeline Limpieza {self.anio}[/]",
            border_style="cyan"
        ))
        t0 = time.time()

        self.paso_cargar()
        self.paso_eliminar_columnas()
        self.paso_parsear_fechas()
        self.paso_anio_desde_fecha()
        self.paso_dia_semana()
        self.paso_cuarto_hora()
        self.paso_limpiar_texto()
        self.paso_eliminar_sin_nombre()
        self.paso_eliminar_velocidades_imposibles()
        self.paso_eliminar_duplicados()
        self.paso_distancia()
        self.paso_renombrar_shape()
        self.paso_numdispositivos()
        self.paso_vel_ponderada()
        self.paso_geocodificar()
        self.paso_ordenar_columnas()
        self.paso_tipos_finales()

        elapsed = time.time() - t0
        console.print(f"\n  [green]Pipeline {self.anio} completado en {elapsed:.1f}s[/]")
        console.print(f"  Shape final: {self.df.shape}")
        console.print(f"  Filas eliminadas: {len(self.df_orig) - len(self.df):,} "
                      f"({(len(self.df_orig)-len(self.df))/len(self.df_orig)*100:.2f}%)")
        return self.df


# ═════════════════════════════════════════════════════════════════════════════
#  REPORTE HTML
# ═════════════════════════════════════════════════════════════════════════════

HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Reporte de Limpieza - Velocidades Bitcarrier</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
  :root{--bg:#0F172A;--surface:#1E293B;--border:#334155;
        --accent:#7C3AED;--green:#10B981;--yellow:#F59E0B;--red:#EF4444;
        --cyan:#06B6D4;--text:#F1F5F9;--muted:#94A3B8;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);padding:2rem;line-height:1.6}
  h1{font-size:1.8rem;font-weight:700;color:var(--accent);margin-bottom:.25rem}
  h2{font-size:1.2rem;font-weight:600;color:var(--cyan);margin:2rem 0 .75rem;
     border-left:3px solid var(--accent);padding-left:.75rem}
  h3{font-size:.95rem;color:var(--yellow);margin:1.2rem 0 .4rem}
  .meta{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
  .kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:1rem;margin:1rem 0}
  .kpi{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1rem;text-align:center}
  .kpi-val{font-size:1.6rem;font-weight:700;color:var(--accent)}
  .kpi-lbl{font-size:.72rem;color:var(--muted);margin-top:.2rem}
  .table-wrap{overflow-x:auto;border-radius:8px;border:1px solid var(--border);margin:.5rem 0}
  table{width:100%;border-collapse:collapse;font-size:.82rem}
  th{background:#2D3748;padding:.45rem .7rem;text-align:left;color:var(--muted);font-weight:600;position:sticky;top:0}
  td{padding:.38rem .7rem;border-bottom:1px solid var(--border)}
  tr:hover td{background:#273444}
  .badge{display:inline-block;padding:.12rem .45rem;border-radius:999px;font-size:.7rem;font-weight:600}
  .b-ok  {background:#052e16;color:var(--green)}
  .b-warn{background:#451a03;color:var(--yellow)}
  .b-err {background:#450a0a;color:var(--red)}
  .insight{background:#1e1b4b;border-left:3px solid var(--accent);border-radius:0 8px 8px 0;
           padding:.85rem 1rem;margin:.6rem 0;font-size:.88rem}
  .insight strong{color:var(--yellow)}
  .sep{border:none;border-top:1px solid var(--border);margin:1.8rem 0}
  .cols-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.4rem;margin:.5rem 0}
  .col-item{background:var(--surface);border:1px solid var(--border);border-radius:6px;
            padding:.4rem .65rem;font-size:.78rem;font-family:monospace}
  footer{text-align:center;color:var(--muted);font-size:.78rem;margin-top:3rem}
</style>
</head>
<body>
<h1>Reporte de Limpieza de Datos</h1>
<p class="meta">Velocidades Bitcarrier Bogota &bull; Generado: {{ fecha_gen }}</p>

{% for ds in datasets %}
<h2>Dataset {{ ds.anio }}</h2>

<div class="kpi-grid">
  <div class="kpi"><div class="kpi-val">{{ "{:,}".format(ds.filas_orig) }}</div><div class="kpi-lbl">Filas originales</div></div>
  <div class="kpi"><div class="kpi-val">{{ "{:,}".format(ds.filas_final) }}</div><div class="kpi-lbl">Filas limpias</div></div>
  <div class="kpi"><div class="kpi-val">{{ ds.pct_retenido }}%</div><div class="kpi-lbl">Datos retenidos</div></div>
  <div class="kpi"><div class="kpi-val">{{ ds.cols_orig }}</div><div class="kpi-lbl">Cols originales</div></div>
  <div class="kpi"><div class="kpi-val">{{ ds.cols_final }}</div><div class="kpi-lbl">Cols finales</div></div>
  <div class="kpi"><div class="kpi-val">{{ ds.pct_geocodificado }}%</div><div class="kpi-lbl">Con lat/lon</div></div>
</div>

<h3>Log del pipeline</h3>
<div class="table-wrap">
<table>
  <thead><tr><th>Paso</th><th>Antes</th><th>Despues</th><th>Eliminados</th><th>%</th><th>Nota</th></tr></thead>
  <tbody>
  {% for paso in ds.log %}
  <tr>
    <td>{{ paso.paso }}</td>
    <td>{{ "{:,}".format(paso.antes) }}</td>
    <td>{{ "{:,}".format(paso.despues) }}</td>
    <td>
      {% if paso.eliminados > 0 %}
        <span class="badge b-warn">-{{ "{:,}".format(paso.eliminados) }}</span>
      {% else %}
        <span class="badge b-ok">0</span>
      {% endif %}
    </td>
    <td>{{ paso.pct_elim }}%</td>
    <td style="color:var(--muted);font-size:.78rem">{{ paso.nota }}</td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>

<h3>Columnas del dataset limpio</h3>
<div class="cols-grid">
{% for col in ds.columnas %}
  <div class="col-item">{{ col }}</div>
{% endfor %}
</div>

<div class="insight">
  <strong>Archivos generados:</strong>
  <code>data/velocidades_{{ ds.anio }}_clean.parquet</code> &bull;
  <code>data/velocidades_{{ ds.anio }}_clean.csv</code>
</div>

{% if not loop.last %}<hr class="sep">{% endif %}
{% endfor %}

<hr class="sep">
<h2>Esquema comun para union de datasets</h2>
<div class="insight">
  <strong>Columna clave de union:</strong> <code>TID</code> (identificador de segmento de via) &bull;
  Ambos datasets comparten el mismo esquema de columnas canonicas.
  Para unir con otros datasets, las claves recomendadas son:
  <code>TID</code>, <code>INICIO</code>, <code>lat</code>/<code>lon</code>.
</div>

<h3>Columnas canonicas compartidas</h3>
<div class="cols-grid">
{% for col in cols_comunes %}
  <div class="col-item">{{ col }}</div>
{% endfor %}
</div>

<h3>Como unir los dos datasets entre si</h3>
<div class="insight">
<pre style="font-size:.8rem;color:var(--cyan)">
import pandas as pd

df22 = pd.read_parquet('data/velocidades_2022_clean.parquet')
df19 = pd.read_parquet('data/velocidades_2019_clean.parquet')

# Union vertical (mismo esquema)
df_todo = pd.concat([df19, df22], ignore_index=True)
df_todo = df_todo.sort_values(['TID','INICIO']).reset_index(drop=True)

# O comparacion por TID y hora (2019 vs 2022)
comparativa = (
    df_todo.groupby(['TID','ANIO','HORA'])['VEL_PROMEDIO']
    .mean().unstack('ANIO').round(2)
)
</pre>
</div>

<footer>DataJam &bull; Pipeline de Limpieza Bitcarrier &bull; {{ fecha_gen }}</footer>
</body>
</html>
"""

def generar_reporte(resultados: list[dict]) -> Path:
    env  = jinja2.Environment(loader=jinja2.BaseLoader())
    tmpl = env.from_string(HTML)
    html = tmpl.render(
        fecha_gen   = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        datasets    = resultados,
        cols_comunes = COLS_FINAL,
    )
    ruta = OUT_DIR / "reporte_limpieza.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    t_total = time.time()
    OUT_DIR.mkdir(exist_ok=True)

    console.print(Panel.fit(
        "[bold magenta]Pipeline de Limpieza - Velocidades Bitcarrier[/]\n"
        "[dim]2019 y 2022  ->  datasets limpios con lat/lon por TID[/]",
        border_style="bright_blue"
    ))

    # ── Cargar tabla de geocodificacion ───────────────────────────────────────
    console.print("\n[bold yellow]Cargando segmentos geocodificados...[/]")
    geo = pd.read_csv(GEO_CSV)
    console.print(f"  [green]OK[/] {len(geo)} TIDs ({geo['lat'].notna().sum()} con coords)")

    resultados_html = []

    for anio, csv_path, cols_drop in [
        (2022, CSV_2022, COLS_ELIMINAR_22),
        (2019, CSV_2019, COLS_ELIMINAR_19),
    ]:
        pipeline = PipelineLimpieza(
            anio=anio, csv_path=csv_path,
            geo=geo, cols_eliminar=cols_drop,
        )
        df_clean = pipeline.ejecutar()

        # ── Guardar como Parquet (recomendado para datos grandes) ─────────────
        out_pq  = DATA_DIR / f"velocidades_{anio}_clean.parquet"
        out_csv = DATA_DIR / f"velocidades_{anio}_clean.csv"

        console.print(f"\n  [bold]Guardando {anio}...[/]")
        df_clean.to_parquet(out_pq, index=False, engine="pyarrow")
        console.print(f"    [green]OK[/] {out_pq}  ({out_pq.stat().st_size/1024/1024:.1f} MB)")
        df_clean.to_csv(out_csv, index=False, encoding="utf-8")
        console.print(f"    [green]OK[/] {out_csv}  ({out_csv.stat().st_size/1024/1024:.1f} MB)")

        # ── Estadisticas para el reporte ──────────────────────────────────────
        pct_geo = round(df_clean["lat"].notna().sum() / len(df_clean) * 100, 1)
        pct_ret = round(len(df_clean) / len(pipeline.df_orig) * 100, 2)

        resultados_html.append({
            "anio":              anio,
            "filas_orig":        len(pipeline.df_orig),
            "filas_final":       len(df_clean),
            "pct_retenido":      pct_ret,
            "cols_orig":         len(pipeline.df_orig.columns),
            "cols_final":        len(df_clean.columns),
            "pct_geocodificado": pct_geo,
            "log": [p for p in pipeline.log],
            "columnas":          df_clean.columns.tolist(),
        })

        # ── Muestra del resultado ─────────────────────────────────────────────
        tabla = Table(box=box.SIMPLE, show_lines=False)
        tabla.add_column("Columna", style="white")
        tabla.add_column("Dtype",   style="dim")
        tabla.add_column("Nulos",   style="yellow", justify="right")
        tabla.add_column("Muestra", style="dim")
        for col in df_clean.columns:
            nulos = df_clean[col].isna().sum()
            muestra = str(df_clean[col].iloc[0])[:35]
            tabla.add_row(col, str(df_clean[col].dtype), f"{nulos:,}", muestra)
        console.print(tabla)

    # ── Reporte HTML ──────────────────────────────────────────────────────────
    console.print("\n[bold yellow]Generando reporte HTML...[/]")
    ruta_html = generar_reporte(resultados_html)
    console.print(f"  [green]OK[/] {ruta_html}")

    # ── Resumen final ─────────────────────────────────────────────────────────
    elapsed = time.time() - t_total
    console.print(Panel.fit(
        f"[bold green]Limpieza completada en {elapsed:.1f}s[/]\n\n"
        "[dim]Archivos generados:[/]\n"
        "  data/velocidades_2022_clean.parquet\n"
        "  data/velocidades_2022_clean.csv\n"
        "  data/velocidades_2019_clean.parquet\n"
        "  data/velocidades_2019_clean.csv\n"
        "  output/reporte_limpieza.html\n\n"
        "[dim]Para cargar en cualquier script:[/]\n"
        "  df = pd.read_parquet('data/velocidades_2022_clean.parquet')",
        border_style="green"
    ))


if __name__ == "__main__":
    main()
