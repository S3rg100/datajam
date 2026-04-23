# -*- coding: utf-8 -*-
"""
=============================================================================
  REFINAMIENTO FINAL - Velocidades Bitcarrier (2019 y 2022)
=============================================================================
  Analiza la calidad de cada columna en los datasets limpios y aplica
  una segunda ronda de depuración basada en:

    1. Columnas con nulos >= umbral configurable
    2. Columnas redundantes (Shape_Length vs DISTANCE_M)
    3. Asimetria entre años (VEL_PONDERADA, NUMDISPOSITIVOS 100% nulas en 2019)

  DECISIONES TOMADAS:

  ELIMINAR (consenso claro):
    - Shape_Length     → redundante con DISTANCE_M (r=0.9936, diff < 7 m)
    - lat_from/lon_from → parcialmente nulas; geometria de linea no esencial
                          para joins. Solo se necesita el centroide (lat/lon).
    - lat_to/lon_to    → misma razon que lat_from/lon_from.

  CONSERVAR con advertencia:
    - VEL_PONDERADA    → 100% nula en 2019, pero valiosa en 2022 para
                          comparativas ponderadas por longitud de tramo.
    - NUMDISPOSITIVOS  → 100% nula en 2019, pero proxy de demanda en 2022.
    - confianza_geo    → clave para filtrar registros sin coordenadas.

  SALIDAS:
    data/velocidades_2022_final.parquet
    data/velocidades_2019_final.parquet
    output/reporte_refinamiento.html
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import jinja2

console = Console()

# ── Rutas ─────────────────────────────────────────────────────────────────────
DATA_DIR      = Path("data")
OUT_DIR       = Path("output")
GFX_DIR       = OUT_DIR / "graficas"

IN_2022       = DATA_DIR / "velocidades_2022_clean.parquet"
IN_2019       = DATA_DIR / "velocidades_2019_clean.parquet"
OUT_2022_PQ   = DATA_DIR / "velocidades_2022_final.parquet"
OUT_2019_PQ   = DATA_DIR / "velocidades_2019_final.parquet"
OUT_2022_CSV  = DATA_DIR / "velocidades_2022_final.csv"
OUT_2019_CSV  = DATA_DIR / "velocidades_2019_final.csv"
OUT_HTML      = OUT_DIR  / "reporte_refinamiento.html"

# ── Configuración ──────────────────────────────────────────────────────────────
BG, SURFACE, ACCENT = "#0F172A", "#1E293B", "#7C3AED"
GREEN, YELLOW, RED, CYAN = "#10B981", "#F59E0B", "#EF4444", "#06B6D4"
MUTED, WHITE = "#94A3B8", "#F1F5F9"

# Columnas que se eliminan DEFINITIVAMENTE en ambos datasets
COLS_ELIMINAR = [
    "Shape_Length",   # Redundante con DISTANCE_M (r=0.9936)
    "lat_from",       # Extremo FROM: parcialmente nulo; centroide (lat/lon) es suficiente
    "lon_from",
    "lat_to",         # Extremo TO: parcialmente nulo
    "lon_to",
]

# ═════════════════════════════════════════════════════════════════════════════
#  BLOQUE 1: ANÁLISIS VISUAL DE NULOS
# ═════════════════════════════════════════════════════════════════════════════

def grafica_nulos(df22: pd.DataFrame, df19: pd.DataFrame) -> str:
    GFX_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), facecolor=BG)

    for ax, df, titulo in [(axes[0], df22, "2022"), (axes[1], df19, "2019")]:
        ax.set_facecolor(SURFACE)
        pct = (df.isnull().sum() / len(df) * 100).sort_values(ascending=True)

        colors = [RED if v > 80 else YELLOW if v > 20 else GREEN for v in pct.values]
        bars = ax.barh(pct.index, pct.values, color=colors, edgecolor="none", height=0.65)

        ax.set_title(f"% Valores nulos — {titulo}", color=WHITE, fontsize=12, pad=10)
        ax.set_xlabel("% Nulos", color=MUTED, fontsize=9)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        ax.set_xlim(0, 105)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(axis="x", color="#334155", linewidth=0.4, linestyle="--", alpha=0.6)
        ax.bar_label(bars, fmt="%.1f%%", color=WHITE, fontsize=7.5, padding=3)

    fig.suptitle("Análisis de valores nulos por columna", color=WHITE, fontsize=13, y=1.01)
    plt.tight_layout()
    ruta = GFX_DIR / "refin_nulos.png"
    fig.savefig(ruta, dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    console.print(f"  [green]v[/] refin_nulos.png")
    return str(ruta.relative_to(OUT_DIR))


def grafica_redundancia(df22: pd.DataFrame) -> str:
    """Scatter DISTANCE_M vs Shape_Length*111000 para probar redundancia."""
    sub = df22[["DISTANCE_M", "Shape_Length"]].dropna().sample(
        min(50_000, len(df22)), random_state=42
    )
    sub["SL_metros"] = sub["Shape_Length"] * 111_000
    corr = sub["DISTANCE_M"].corr(sub["SL_metros"])

    fig, ax = plt.subplots(figsize=(7, 6), facecolor=BG)
    ax.set_facecolor(SURFACE)
    ax.hexbin(sub["DISTANCE_M"], sub["SL_metros"], gridsize=50,
              cmap="viridis", mincnt=1)
    # Línea perfecta y=x
    lim = max(sub["DISTANCE_M"].max(), sub["SL_metros"].max())
    ax.plot([0, lim], [0, lim], color=RED, lw=1.5, linestyle="--",
            label="y = x (perfecta)")
    ax.set_xlabel("DISTANCE_M (metros)", color=MUTED, fontsize=9)
    ax.set_ylabel("Shape_Length × 111,000 (metros equiv.)", color=MUTED, fontsize=9)
    ax.set_title(f"Redundancia Shape_Length vs DISTANCE_M\nr = {corr:.4f}",
                 color=WHITE, fontsize=11, pad=10)
    ax.tick_params(colors=MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.legend(facecolor=SURFACE, labelcolor=WHITE, fontsize=9)

    ruta = GFX_DIR / "refin_redundancia.png"
    fig.savefig(ruta, dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    console.print(f"  [green]v[/] refin_redundancia.png")
    return str(ruta.relative_to(OUT_DIR))


def grafica_cobertura_geo(df22: pd.DataFrame, df19: pd.DataFrame) -> str:
    """Barras apiladas: registros con coords / sin coords por año."""
    data = {
        "Año": ["2022", "2019"],
        "Con lat/lon": [df22["lat"].notna().sum(), df19["lat"].notna().sum()],
        "Sin lat/lon":  [df22["lat"].isna().sum(),  df19["lat"].isna().sum()],
    }
    df_plot = pd.DataFrame(data)
    total22, total19 = len(df22), len(df19)

    fig, ax = plt.subplots(figsize=(8, 4), facecolor=BG)
    ax.set_facecolor(SURFACE)
    ax.barh(df_plot["Año"], df_plot["Con lat/lon"], color=GREEN,
            label="Con lat/lon", edgecolor="none")
    ax.barh(df_plot["Año"], df_plot["Sin lat/lon"],
            left=df_plot["Con lat/lon"], color=RED,
            label="Sin lat/lon", edgecolor="none")

    for i, (con, sin, total) in enumerate(zip(
        df_plot["Con lat/lon"], df_plot["Sin lat/lon"],
        [total22, total19]
    )):
        ax.text(con / 2, i, f"{con/total*100:.1f}%", va="center",
                ha="center", color=WHITE, fontsize=11, fontweight="bold")
        ax.text(con + sin / 2, i, f"{sin/total*100:.1f}%", va="center",
                ha="center", color=WHITE, fontsize=11, fontweight="bold")

    ax.set_xlabel("Registros", color=MUTED, fontsize=9)
    ax.set_title("Cobertura geográfica (lat/lon) por dataset", color=WHITE,
                 fontsize=11, pad=10)
    ax.tick_params(colors=MUTED, labelsize=9)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    ax.legend(facecolor=SURFACE, labelcolor=WHITE, fontsize=9)

    ruta = GFX_DIR / "refin_cobertura_geo.png"
    fig.savefig(ruta, dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    console.print(f"  [green]v[/] refin_cobertura_geo.png")
    return str(ruta.relative_to(OUT_DIR))


# ═════════════════════════════════════════════════════════════════════════════
#  BLOQUE 2: TABLA DE AUDITORÍA COMPLETA
# ═════════════════════════════════════════════════════════════════════════════

def auditar(df22: pd.DataFrame, df19: pd.DataFrame) -> list[dict]:
    """Genera tabla de diagnóstico columna×año con recomendación."""
    todas_cols = sorted(set(df22.columns) | set(df19.columns))
    filas = []

    for col in todas_cols:
        p22 = df22[col].isna().sum() / len(df22) * 100 if col in df22.columns else None
        p19 = df19[col].isna().sum() / len(df19) * 100 if col in df19.columns else None
        u22 = int(df22[col].nunique()) if col in df22.columns else None
        u19 = int(df19[col].nunique()) if col in df19.columns else None

        if col in COLS_ELIMINAR:
            rec = "ELIMINAR"
            razon = ("Redundante con DISTANCE_M" if col == "Shape_Length"
                     else "Extremo de tramo; centroide (lat/lon) es suficiente")
        elif col in ("VEL_PONDERADA", "NUMDISPOSITIVOS"):
            rec = "CONSERVAR*"
            razon = "100% nulo en 2019 / valioso en 2022; no se elimina"
        elif col == "confianza_geo":
            rec = "CONSERVAR"
            razon = "Indica calidad del dato espacial"
        elif (p22 is not None and p22 > 90) and (p19 is not None and p19 > 90):
            rec = "ELIMINAR"
            razon = f">{int(max(p22, p19))}% nulos en ambos años"
        else:
            rec = "CONSERVAR"
            razon = "Dato válido y con información"

        filas.append({
            "columna":  col,
            "nulo_22":  round(p22, 1) if p22 is not None else None,
            "nulo_19":  round(p19, 1) if p19 is not None else None,
            "unicos_22": u22,
            "unicos_19": u19,
            "rec":       rec,
            "razon":     razon,
        })
    return filas


def imprimir_audit_consola(filas: list[dict]):
    t = Table(title="Auditoría de columnas", box=box.ROUNDED, show_lines=True)
    t.add_column("Columna",    style="white")
    t.add_column("2022 %null", justify="right")
    t.add_column("2019 %null", justify="right")
    t.add_column("Únicos 22",  justify="right", style="dim")
    t.add_column("Dec.",       style="bold")
    t.add_column("Razón",      style="dim")

    for f in filas:
        p22 = f"{f['nulo_22']:.1f}%" if f["nulo_22"] is not None else "N/A"
        p19 = f"{f['nulo_19']:.1f}%" if f["nulo_19"] is not None else "N/A"
        color_rec = (
            "[red]" if f["rec"] == "ELIMINAR"
            else "[yellow]" if f["rec"].startswith("CONSERVAR*")
            else "[green]"
        )
        t.add_row(f["columna"], p22, p19,
                  str(f["unicos_22"]) if f["unicos_22"] is not None else "N/A",
                  f"{color_rec}{f['rec']}[/]", f["razon"])
    console.print(t)


# ═════════════════════════════════════════════════════════════════════════════
#  BLOQUE 3: APLICAR REFINAMIENTO
# ═════════════════════════════════════════════════════════════════════════════

def refinar(df: pd.DataFrame, anio: int) -> pd.DataFrame:
    console.print(f"\n  [bold]Refinando {anio}...[/]")
    cols_a_drop = [c for c in COLS_ELIMINAR if c in df.columns]
    df = df.drop(columns=cols_a_drop)
    console.print(f"  [green]OK[/] Eliminadas: {cols_a_drop}")
    console.print(f"  Shape resultante: {df.shape}  |  Columnas: {df.columns.tolist()}")
    return df


# ═════════════════════════════════════════════════════════════════════════════
#  REPORTE HTML
# ═════════════════════════════════════════════════════════════════════════════

HTML_TPL = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Refinamiento Final - Velocidades Bitcarrier</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
  :root{--bg:#0F172A;--surface:#1E293B;--border:#334155;
        --accent:#7C3AED;--green:#10B981;--yellow:#F59E0B;--red:#EF4444;
        --cyan:#06B6D4;--text:#F1F5F9;--muted:#94A3B8;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);
       padding:2rem;line-height:1.6}
  h1{font-size:1.8rem;font-weight:700;
     background:linear-gradient(90deg,var(--accent),var(--cyan));
     -webkit-background-clip:text;-webkit-text-fill-color:transparent;
     margin-bottom:.25rem}
  h2{font-size:1.15rem;font-weight:600;color:var(--cyan);margin:2rem 0 .75rem;
     border-left:3px solid var(--accent);padding-left:.75rem}
  h3{font-size:.95rem;color:var(--yellow);margin:1.2rem 0 .4rem}
  .meta{color:var(--muted);font-size:.85rem;margin-bottom:2rem}
  .kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin:1rem 0}
  .kpi{background:var(--surface);border:1px solid var(--border);border-radius:10px;
       padding:1rem;text-align:center}
  .kpi-val{font-size:1.5rem;font-weight:700;color:var(--accent)}
  .kpi-lbl{font-size:.72rem;color:var(--muted);margin-top:.2rem}
  .table-wrap{overflow-x:auto;border-radius:8px;border:1px solid var(--border);margin:.5rem 0}
  table{width:100%;border-collapse:collapse;font-size:.82rem}
  th{background:#2D3748;padding:.45rem .7rem;text-align:left;color:var(--muted);font-weight:600}
  td{padding:.38rem .7rem;border-bottom:1px solid var(--border)}
  tr:hover td{background:#273444}
  .elim{background:#450a0a;color:var(--red);border-radius:4px;
        padding:.1rem .4rem;font-weight:700;font-size:.75rem}
  .cons{background:#052e16;color:var(--green);border-radius:4px;
        padding:.1rem .4rem;font-weight:700;font-size:.75rem}
  .warn{background:#451a03;color:var(--yellow);border-radius:4px;
        padding:.1rem .4rem;font-weight:700;font-size:.75rem}
  .grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));
           gap:1.5rem;margin:1rem 0}
  .card{background:var(--surface);border:1px solid var(--border);
        border-radius:12px;overflow:hidden}
  .card img{width:100%;display:block}
  .card-title{padding:.55rem 1rem;font-size:.8rem;color:var(--muted)}
  .insight{background:#1e1b4b;border-left:3px solid var(--accent);
           border-radius:0 8px 8px 0;padding:.85rem 1rem;margin:.6rem 0;
           font-size:.88rem}
  .insight strong{color:var(--yellow)}
  .schema{display:grid;grid-template-columns:repeat(auto-fill,minmax(195px,1fr));
          gap:.35rem;margin:.5rem 0}
  .col-chip{background:var(--surface);border:1px solid var(--border);
            border-radius:6px;padding:.35rem .6rem;font-size:.78rem;font-family:monospace}
  pre{font-size:.8rem;color:var(--cyan);background:#0d1526;border-radius:8px;
      padding:1rem;overflow-x:auto;margin:.5rem 0}
  footer{text-align:center;color:var(--muted);font-size:.78rem;margin-top:3rem}
  .sep{border:none;border-top:1px solid var(--border);margin:2rem 0}
</style>
</head>
<body>
<h1>Refinamiento Final de Datasets</h1>
<p class="meta">Velocidades Bitcarrier Bogotá &bull; Generado: {{ fecha }}</p>

<h2>Resumen ejecutivo</h2>
<div class="kpi-grid">
  <div class="kpi"><div class="kpi-val">{{ cols_eliminadas }}</div>
    <div class="kpi-lbl">Columnas eliminadas</div></div>
  <div class="kpi"><div class="kpi-val">{{ cols_final }}</div>
    <div class="kpi-lbl">Columnas finales</div></div>
  <div class="kpi"><div class="kpi-val">{{ "{:,}".format(filas_22) }}</div>
    <div class="kpi-lbl">Filas 2022</div></div>
  <div class="kpi"><div class="kpi-val">{{ "{:,}".format(filas_19) }}</div>
    <div class="kpi-lbl">Filas 2019</div></div>
  <div class="kpi"><div class="kpi-val">{{ pct_geo_22 }}%</div>
    <div class="kpi-lbl">Con lat/lon (2022)</div></div>
  <div class="kpi"><div class="kpi-val">{{ pct_geo_19 }}%</div>
    <div class="kpi-lbl">Con lat/lon (2019)</div></div>
</div>

<div class="insight">
  <strong>Decisión clave:</strong> Se eliminaron <strong>{{ cols_eliminadas }} columnas</strong>:
  <code>Shape_Length</code> (redundante con DISTANCE_M, r=0.99),
  <code>lat_from</code>, <code>lon_from</code>, <code>lat_to</code>, <code>lon_to</code>
  (extremos de tramo; el centroide <code>lat</code>/<code>lon</code> es suficiente para joins espaciales).
  <br><br>Se conservaron <code>VEL_PONDERADA</code> y <code>NUMDISPOSITIVOS</code>
  aunque estén vacías en 2019, ya que son métricas clave en 2022.
</div>

<h2>Análisis visual</h2>
<div class="grid-2">
  <div class="card"><img src="{{ gfx_nulos }}" alt="Nulos"><div class="card-title">% Nulos por columna en cada dataset</div></div>
  <div class="card"><img src="{{ gfx_redundancia }}" alt="Redundancia"><div class="card-title">Shape_Length vs DISTANCE_M: correlación r=0.9936 — columna eliminada</div></div>
</div>
<div class="grid-2">
  <div class="card"><img src="{{ gfx_geo }}" alt="Cobertura geo"><div class="card-title">Cobertura de coordenadas lat/lon por dataset</div></div>
</div>

<hr class="sep">
<h2>Tabla de decisiones por columna</h2>
<div class="table-wrap">
<table>
  <thead>
    <tr><th>Columna</th><th>2022 % nulo</th><th>2019 % nulo</th>
        <th>Únicos 22</th><th>Decisión</th><th>Razón</th></tr>
  </thead>
  <tbody>
  {% for f in filas %}
  <tr>
    <td><b>{{ f.columna }}</b></td>
    <td>{{ f.nulo_22 if f.nulo_22 is not none else 'N/A' }}%</td>
    <td>{{ f.nulo_19 if f.nulo_19 is not none else 'N/A' }}%</td>
    <td>{{ f.unicos_22 if f.unicos_22 is not none else 'N/A' }}</td>
    <td>
      {% if f.rec == 'ELIMINAR' %}<span class="elim">ELIMINAR</span>
      {% elif f.rec.startswith('CONSERVAR*') %}<span class="warn">CONSERVAR*</span>
      {% else %}<span class="cons">CONSERVAR</span>{% endif %}
    </td>
    <td style="color:var(--muted);font-size:.78rem">{{ f.razon }}</td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
<p style="font-size:.78rem;color:var(--muted);margin-top:.4rem">* CONSERVAR* = vacío en 2019 pero valioso en 2022</p>

<hr class="sep">
<h2>Schema final ({{ cols_final }} columnas)</h2>
<div class="schema">
{% for col in schema_final %}
  <div class="col-chip">{{ col }}</div>
{% endfor %}
</div>

<h2>Cómo usar los datasets finales</h2>
<pre>
import pandas as pd

# Cargar
df22 = pd.read_parquet('data/velocidades_2022_final.parquet')
df19 = pd.read_parquet('data/velocidades_2019_final.parquet')

# Union vertical (mismo esquema)
df_todo = pd.concat([df19, df22], ignore_index=True)
df_todo = df_todo.sort_values(['TID', 'INICIO'])

# Filtrar solo registros con coordenadas válidas
df22_geo = df22.dropna(subset=['lat', 'lon'])

# JOIN con otro dataset por TID
df_enriquecido = df22.merge(otro_dataset, on='TID', how='left')

# Comparativa 2019 vs 2022 por corredor y hora
pivot = (
    df_todo.groupby(['NAME_FROM', 'ANIO', 'HORA'])['VEL_PROMEDIO']
    .mean().unstack('ANIO').round(2)
)
</pre>

<footer>DataJam &bull; Refinamiento Final Bitcarrier &bull; {{ fecha }}</footer>
</body>
</html>
"""


def generar_html(filas, schema_final, gfx_nulos, gfx_red, gfx_geo,
                 df22_f, df19_f) -> Path:
    env  = jinja2.Environment(loader=jinja2.BaseLoader())
    tmpl = env.from_string(HTML_TPL)
    html = tmpl.render(
        fecha           = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        cols_eliminadas = len(COLS_ELIMINAR),
        cols_final      = len(schema_final),
        filas_22        = len(df22_f),
        filas_19        = len(df19_f),
        pct_geo_22      = round(df22_f["lat"].notna().sum() / len(df22_f) * 100, 1),
        pct_geo_19      = round(df19_f["lat"].notna().sum() / len(df19_f) * 100, 1),
        filas           = filas,
        schema_final    = schema_final,
        gfx_nulos       = gfx_nulos,
        gfx_redundancia = gfx_red,
        gfx_geo         = gfx_geo,
    )
    OUT_HTML.write_text(html, encoding="utf-8")
    return OUT_HTML


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()
    OUT_DIR.mkdir(exist_ok=True)
    GFX_DIR.mkdir(exist_ok=True)

    console.print(Panel.fit(
        "[bold magenta]Refinamiento Final - Velocidades Bitcarrier[/]\n"
        "[dim]Analisis de nulos, redundancia y depuracion de columnas[/]",
        border_style="bright_blue"
    ))

    # ── Cargar datasets limpios ───────────────────────────────────────────────
    console.print("\n[bold yellow]Cargando datasets limpios...[/]")
    df22 = pd.read_parquet(IN_2022)
    df19 = pd.read_parquet(IN_2019)
    console.print(f"  2022: {df22.shape}   2019: {df19.shape}")

    # ── Auditoría ─────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]Auditando columnas...[/]")
    filas_audit = auditar(df22, df19)
    imprimir_audit_consola(filas_audit)

    # ── Gráficas ──────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]Generando graficas...[/]")
    gfx_nulos = grafica_nulos(df22, df19)
    gfx_red   = grafica_redundancia(df22)
    gfx_geo   = grafica_cobertura_geo(df22, df19)

    # ── Refinar ───────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]Aplicando refinamiento...[/]")
    df22_f = refinar(df22, 2022)
    df19_f = refinar(df19, 2019)

    # ── Guardar ───────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]Guardando archivos finales...[/]")
    df22_f.to_parquet(OUT_2022_PQ, index=False, engine="pyarrow")
    df19_f.to_parquet(OUT_2019_PQ, index=False, engine="pyarrow")
    df22_f.to_csv(OUT_2022_CSV, index=False, encoding="utf-8")
    df19_f.to_csv(OUT_2019_CSV, index=False, encoding="utf-8")

    for p in [OUT_2022_PQ, OUT_2019_PQ, OUT_2022_CSV, OUT_2019_CSV]:
        console.print(f"  [green]OK[/] {p}  ({p.stat().st_size/1024/1024:.1f} MB)")

    # ── Reporte ───────────────────────────────────────────────────────────────
    console.print("\n[bold yellow]Generando reporte HTML...[/]")
    ruta_html = generar_html(
        filas_audit, df22_f.columns.tolist(),
        gfx_nulos, gfx_red, gfx_geo,
        df22_f, df19_f
    )
    console.print(f"  [green]OK[/] {ruta_html}")

    # ── Resumen final ─────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    console.print(Panel.fit(
        f"[bold green]Refinamiento completado en {elapsed:.1f}s[/]\n\n"
        f"[dim]Columnas eliminadas: {COLS_ELIMINAR}[/]\n\n"
        "[dim]Archivos finales:[/]\n"
        f"  {OUT_2022_PQ}\n  {OUT_2019_PQ}\n"
        f"  {OUT_2022_CSV}\n  {OUT_2019_CSV}\n"
        f"  {ruta_html}",
        border_style="green"
    ))


if __name__ == "__main__":
    main()
