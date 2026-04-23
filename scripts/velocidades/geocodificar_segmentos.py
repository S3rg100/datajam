# -*- coding: utf-8 -*-
"""
=============================================================================
  GEOCODIFICACION DE SEGMENTOS - Velocidades Bitcarrier Bogota
=============================================================================
  El CSV de velocidades NO tiene lat/lon directa. Cada registro se identifica
  por un TID (segmento de red vial) y el par NAME_FROM -> NAME_TO.

  Este script genera coordenadas para cada TID mediante Nominatim
  (OpenStreetMap), buscando las intersecciones en Bogota.

  ESTRATEGIA:
    1. Extraer los 663 TIDs unicos con sus NAME_FROM / NAME_TO
    2. Geocodificar NAME_FROM (interseccion origen) via Nominatim OSM
    3. Geocodificar NAME_TO   (interseccion destino) via Nominatim OSM
    4. Calcular el centroide del tramo   = (FROM + TO) / 2
    5. Guardar tabla de referencia:  data/segmentos_geocodificados.csv
    6. Hacer JOIN con el CSV de velocidades y guardar muestra enriquecida
    7. Generar mapa interactivo con los segmentos geolocalizados

  SALIDAS:
    data/segmentos_geocodificados.csv    <- tabla de referencia TID -> lat/lon
    output/mapa_velocidades_tramos.html  <- mapa interactivo
=============================================================================
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import time
import json
import warnings
import re
warnings.filterwarnings("ignore")

from pathlib import Path
import pandas as pd
import requests
import folium
from folium.plugins import HeatMap, MarkerCluster, Fullscreen, MiniMap
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from rich.table import Table
from rich import box

console = Console()

CSV_2022   = Path("data/Velocidades_Bitcarrier_Octubre_2022_5740524589707522675.csv")
OUT_SEGS   = Path("data/segmentos_geocodificados.csv")
OUT_MAPA   = Path("output/mapa_velocidades_tramos.html")
OUT_DIR    = Path("output")

# Nominatim: maximo 1 req/seg (politica de uso)
NOMINATIM_URL  = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HDR  = {"User-Agent": "DataJam-Bogota-Velocidades/1.0"}
DELAY_SEG      = 1.1   # espera entre requests

# Bounding box de Bogota (para acotar la busqueda)
BOGOTA_VIEWBOX = "-74.35,4.45,-73.98,4.85"   # lon_min,lat_min,lon_max,lat_max
BOGOTA_COUNTRYCODES = "co"

# Colores para el mapa segun velocidad media
def color_velocidad(v: float) -> str:
    if v < 15:   return "#EF4444"   # rojo      - congestion severa
    if v < 25:   return "#F97316"   # naranja   - lento
    if v < 35:   return "#F59E0B"   # amarillo  - normal
    if v < 45:   return "#84CC16"   # verde lima
    return         "#10B981"         # verde     - fluido


# ── Parseo de nombres de interseccion de Bogota ────────────────────────────────
# Bogota usa nomenclatura: KR7, CL134, AV.BOYACA, NQS, AUTONORTE, etc.
# Nominatim entiende nombres en espanol y "Carrera 7", "Calle 134", etc.

EXPAND = {
    r"^KR(\d+)$":           r"Carrera \1",
    r"^CL(\d+\w*)$":        r"Calle \1",
    r"^DIAG(\d+\w*)$":      r"Diagonal \1",
    r"^TV(\d+)$":           r"Transversal \1",
    r"^AK(\d+)$":           r"Avenida Carrera \1",
    r"^AV\.BOYACA$":        "Avenida Boyaca",
    r"^AV\.CARACAS$":       "Avenida Caracas",
    r"^AV\.AMERICAS$":      "Avenida de las Americas",
    r"^AV\.SUBA$":          "Avenida Suba",
    r"^AV\.CORDOBA$":       "Avenida Cordoba",
    r"^AV\.P\.MAYO$":       "Avenida Primero de Mayo",
    r"^AV\.CL127$":         "Avenida Calle 127",
    r"^AV\.CL59SUR$":       "Avenida Calle 59 Sur",
    r"^AUTONORTE$":         "Autopista Norte",
    r"^AUTOPISTASUR$":      "Autopista Sur",
    r"^NQS$":               "NQS",
    r"^CARACAS$":           "Avenida Caracas",
    r"^AV\.DORADO$":        "Avenida El Dorado",
    r"^AV\.CIRCUNVALAR$":   "Avenida Circunvalar",
    r"^BOYACA$":            "Avenida Boyaca",
}

def expandir_nombre(raw: str) -> str:
    """Convierte abreviaturas de Bogota a nombres legibles para Nominatim."""
    name = str(raw).strip().upper().replace(" ", "")
    for pattern, replacement in EXPAND.items():
        result = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
        if result != name:
            return result
    return name.replace(".", " ").title()


def geocodificar(nombre: str, reintentos: int = 2) -> tuple[float, float] | None:
    """Geocodifica un nombre de via en Bogota. Retorna (lat, lon) o None."""
    query = f"{nombre}, Bogota, Colombia"
    for intento in range(reintentos + 1):
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={
                    "q":            query,
                    "format":       "json",
                    "limit":        1,
                    "countrycodes": BOGOTA_COUNTRYCODES,
                    "viewbox":      BOGOTA_VIEWBOX,
                    "bounded":      1,
                },
                headers=NOMINATIM_HDR,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as e:
            if intento < reintentos:
                time.sleep(2)
    return None


# ── Carga de datos ─────────────────────────────────────────────────────────────

def cargar_segmentos() -> pd.DataFrame:
    """Extrae los 663 TIDs unicos con sus atributos de nombre."""
    console.print("[bold yellow]Cargando CSV de velocidades...[/]")
    df = pd.read_csv(CSV_2022, low_memory=False)

    seg = (
        df.groupby("TID")
        .agg(
            NAME_FROM    = ("NAME_FROM",  "first"),
            NAME_TO      = ("NAME_TO",    "first"),
            DISTANCE_m   = ("DISTANCE",   "first"),
            VEL_MEDIA    = ("VEL_PROMEDIO", "mean"),
            VEL_PICO     = ("VEL_PROMEDIO", lambda x:
                            x[df.loc[x.index, "HORA"].isin(range(6,9)) |
                              df.loc[x.index, "HORA"].isin(range(17,20))].mean()),
            N_REGISTROS  = ("OBJECTID", "count"),
        )
        .reset_index()
    )
    seg = seg.dropna(subset=["NAME_FROM"])  # los 21 sin nombre se descartan
    console.print(f"  [green]OK[/] {len(seg)} segmentos unicos con nombre")
    return seg


# ── Geocodificacion ────────────────────────────────────────────────────────────

def geocodificar_segmentos(seg: pd.DataFrame) -> pd.DataFrame:
    """
    Geocodifica NAME_FROM y el primer elemento de NAME_TO para cada TID.
    Respeta el rate-limit de Nominatim (1 req/seg).
    """
    # Si ya existe el archivo cacheado, usarlo
    if OUT_SEGS.exists():
        console.print(f"\n[bold green]Cache encontrado:[/] {OUT_SEGS}")
        console.print("  Cargando coordenadas previas...")
        cached = pd.read_csv(OUT_SEGS)
        console.print(f"  [green]OK[/] {len(cached)} segmentos con coordenadas")
        return cached

    console.print(f"\n[bold yellow]Geocodificando {len(seg)} segmentos via Nominatim OSM...[/]")
    console.print("[dim]  (aprox. 1 request/seg por politica de uso -> puede tardar ~22 min)[/]")
    console.print("[dim]  El resultado se guardara en cache para no repetir.[/]\n")

    resultados = []

    for i, row in enumerate(seg.itertuples(), 1):
        # -- Geocodificar NAME_FROM --
        nombre_from = expandir_nombre(row.NAME_FROM)
        coord_from  = geocodificar(nombre_from)
        time.sleep(DELAY_SEG)

        # -- Geocodificar primera interseccion de NAME_TO --
        to_raw     = str(row.NAME_TO).split(";")[0].split(",")[0].strip()
        nombre_to  = expandir_nombre(to_raw)
        coord_to   = geocodificar(nombre_to)
        time.sleep(DELAY_SEG)

        # -- Calcular centroide del tramo --
        lat_from = coord_from[0] if coord_from else None
        lon_from = coord_from[1] if coord_from else None
        lat_to   = coord_to[0]  if coord_to   else None
        lon_to   = coord_to[1]  if coord_to   else None

        # Centroide: promedio de FROM y TO si ambos disponibles, si no el que haya
        if lat_from and lat_to:
            lat_c = (lat_from + lat_to) / 2
            lon_c = (lon_from + lon_to) / 2
            confianza = "alta"
        elif lat_from:
            lat_c, lon_c = lat_from, lon_from
            confianza = "media"
        elif lat_to:
            lat_c, lon_c = lat_to, lon_to
            confianza = "media"
        else:
            lat_c = lon_c = None
            confianza = "sin_coords"

        resultados.append({
            "TID":         row.TID,
            "NAME_FROM":   row.NAME_FROM,
            "NAME_TO":     row.NAME_TO,
            "DISTANCE_m":  row.DISTANCE_m,
            "VEL_MEDIA":   round(row.VEL_MEDIA, 2) if pd.notna(row.VEL_MEDIA) else None,
            "VEL_PICO":    round(row.VEL_PICO, 2)  if pd.notna(row.VEL_PICO)  else None,
            "N_REGISTROS": row.N_REGISTROS,
            "lat_from":    lat_from,
            "lon_from":    lon_from,
            "lat_to":      lat_to,
            "lon_to":      lon_to,
            "lat":         lat_c,
            "lon":         lon_c,
            "confianza":   confianza,
            "query_from":  nombre_from,
            "query_to":    nombre_to,
        })

        if i % 20 == 0:
            console.print(f"  [{i}/{len(seg)}] procesados... {sum(1 for r in resultados if r['lat'] is not None)} con coords")
            # Guardar parcialmente
            pd.DataFrame(resultados).to_csv(OUT_SEGS, index=False)

    df_result = pd.DataFrame(resultados)
    df_result.to_csv(OUT_SEGS, index=False)
    ok = df_result["lat"].notna().sum()
    console.print(f"\n  [green]OK[/] {ok}/{len(df_result)} segmentos geocodificados ({ok/len(df_result)*100:.1f}%)")
    return df_result


# ── Mapa interactivo ───────────────────────────────────────────────────────────

def generar_mapa(seg_geo: pd.DataFrame):
    """Genera mapa Folium con los tramos coloreados por velocidad media."""
    validos = seg_geo.dropna(subset=["lat", "lon"])
    # Filtrar puntos fuera de Bogota
    validos = validos[
        (validos["lat"].between(4.4, 4.9)) &
        (validos["lon"].between(-74.4, -73.9))
    ]
    console.print(f"\n  Segmentos dentro de Bogota: {len(validos)}/{len(seg_geo)}")

    center_lat = validos["lat"].median()
    center_lon = validos["lon"].median()

    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles=None)

    # Capas base
    folium.TileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="CartoDB", name="Mapa Oscuro"
    ).add_to(m)
    folium.TileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="OpenStreetMap", name="OpenStreetMap"
    ).add_to(m)

    Fullscreen(position="topright").add_to(m)
    MiniMap(toggle_display=True, position="bottomright").add_to(m)

    # ── Capa 1: Circulos por velocidad media ──────────────────────────────────
    capa_vel = folium.FeatureGroup(name="Velocidad media (todos los horarios)", show=True)
    for _, row in validos.iterrows():
        vel   = row["VEL_MEDIA"]
        color = color_velocidad(vel) if pd.notna(vel) else "#6B7280"
        radio = max(5, min(14, row["DISTANCE_m"] / 120)) if pd.notna(row["DISTANCE_m"]) else 6

        popup_html = f"""
        <div style="font-family:'Segoe UI',sans-serif;min-width:230px;
                    background:#1E293B;color:#F1F5F9;border-radius:10px;padding:12px;">
            <div style="border-left:3px solid {color};padding-left:8px;margin-bottom:10px;">
                <b style="color:{color};font-size:13px;">{row['NAME_FROM']}</b>
                <div style="font-size:10px;color:#94A3B8;">TID: {int(row['TID'])}</div>
            </div>
            <div style="font-size:11px;">
                <b>Destino:</b> {row['NAME_TO']}<br>
                <b>Longitud:</b> {int(row['DISTANCE_m']) if pd.notna(row['DISTANCE_m']) else '?'} m<br>
                <b>Vel. media:</b> <span style="color:{color};font-weight:700;">{vel:.1f} km/h</span><br>
                <b>Vel. pico:</b> {row['VEL_PICO']:.1f if pd.notna(row['VEL_PICO']) else '?'} km/h<br>
                <b>Registros:</b> {int(row['N_REGISTROS']):,}<br>
                <b>Confianza GPS:</b> {row['confianza']}
            </div>
        </div>
        """
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=radio,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            weight=1.5,
            tooltip=f"<b>{row['NAME_FROM']}</b> → {str(row['NAME_TO'])[:30]}<br>{vel:.1f} km/h",
            popup=folium.Popup(popup_html, max_width=260),
        ).add_to(capa_vel)
    capa_vel.add_to(m)

    # ── Capa 2: Heatmap de velocidad (invertido: lentos = caliente) ───────────
    heat_data = [
        [row["lat"], row["lon"], max(0, 60 - row["VEL_MEDIA"])]   # invertir: rojo = lento
        for _, row in validos.iterrows()
        if pd.notna(row["VEL_MEDIA"])
    ]
    HeatMap(
        heat_data,
        name="Heatmap de congestion (rojo = lento)",
        radius=25, blur=18, min_opacity=0.3,
        gradient={0.3: "#10B981", 0.6: "#F59E0B", 1.0: "#EF4444"},
        show=False,
    ).add_to(m)

    # ── Capa 3: Top 15 tramos mas lentos ─────────────────────────────────────
    capa_lentos = folium.FeatureGroup(name="Top 15 tramos mas lentos", show=False)
    lentos = validos.nsmallest(15, "VEL_MEDIA")
    for rank, (_, row) in enumerate(lentos.iterrows(), 1):
        folium.Marker(
            location=[row["lat"], row["lon"]],
            tooltip=f"#{rank} MAS LENTO: {row['NAME_FROM']} → {str(row['NAME_TO'])[:25]} | {row['VEL_MEDIA']:.1f} km/h",
            icon=folium.DivIcon(
                html=f"""<div style="background:#EF4444;color:white;border-radius:50%;
                                     width:24px;height:24px;display:flex;align-items:center;
                                     justify-content:center;font-weight:bold;font-size:11px;
                                     border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.5)">
                          {rank}</div>""",
                icon_size=(24, 24),
                icon_anchor=(12, 12),
            ),
        ).add_to(capa_lentos)
    capa_lentos.add_to(m)

    # ── Leyenda ───────────────────────────────────────────────────────────────
    legend = """
    <div style="position:fixed;bottom:60px;left:20px;z-index:1000;
                background:rgba(15,23,42,0.93);border:1px solid #334155;
                border-radius:12px;padding:14px 18px;
                font-family:'Segoe UI',sans-serif;color:#F1F5F9;min-width:170px;
                box-shadow:0 4px 20px rgba(0,0,0,0.5);">
        <b style="color:#7C3AED;font-size:13px;">Velocidad media</b>
        <div style="margin-top:8px;font-size:11px;">
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0">
                <div style="width:12px;height:12px;border-radius:50%;background:#EF4444"></div> &lt;15 km/h — Congestion
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0">
                <div style="width:12px;height:12px;border-radius:50%;background:#F97316"></div> 15-25 km/h — Lento
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0">
                <div style="width:12px;height:12px;border-radius:50%;background:#F59E0B"></div> 25-35 km/h — Normal
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0">
                <div style="width:12px;height:12px;border-radius:50%;background:#84CC16"></div> 35-45 km/h — Fluido
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin:4px 0">
                <div style="width:12px;height:12px;border-radius:50%;background:#10B981"></div> &gt;45 km/h — Rapido
            </div>
        </div>
        <hr style="border-color:#334155;margin:8px 0">
        <div style="font-size:10px;color:#64748B;">Tamano del circulo = longitud del tramo</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    OUT_DIR.mkdir(exist_ok=True)
    m.save(str(OUT_MAPA))
    return m, len(validos)


# ── Estadisticas finales ───────────────────────────────────────────────────────

def imprimir_estadisticas(seg_geo: pd.DataFrame):
    validos = seg_geo.dropna(subset=["lat","lon"])
    validos = validos[validos["lat"].between(4.4, 4.9) & validos["lon"].between(-74.4, -73.9)]

    tabla = Table(title="Segmentos geocodificados", box=box.ROUNDED, show_lines=True)
    tabla.add_column("Indicador", style="bold white")
    tabla.add_column("Valor",     style="yellow")
    tabla.add_row("Total TIDs",          str(len(seg_geo)))
    tabla.add_row("Con coordenadas",     str(validos.shape[0]))
    tabla.add_row("Sin coordenadas",     str(seg_geo["lat"].isna().sum()))
    tabla.add_row("Confianza alta",      str((seg_geo["confianza"]=="alta").sum()))
    tabla.add_row("Confianza media",     str((seg_geo["confianza"]=="media").sum()))
    tabla.add_row("Vel. media global",   f"{validos['VEL_MEDIA'].mean():.1f} km/h")
    tabla.add_row("Tramo mas lento",
                  validos.loc[validos['VEL_MEDIA'].idxmin(), 'NAME_FROM']
                  + " -> " +
                  str(validos.loc[validos['VEL_MEDIA'].idxmin(), 'NAME_TO'])[:30])
    tabla.add_row("Tramo mas rapido",
                  validos.loc[validos['VEL_MEDIA'].idxmax(), 'NAME_FROM']
                  + " -> " +
                  str(validos.loc[validos['VEL_MEDIA'].idxmax(), 'NAME_TO'])[:30])
    console.print(tabla)


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    OUT_DIR.mkdir(exist_ok=True)
    console.print(Panel.fit(
        "[bold magenta]Geocodificacion de Segmentos Viales - Bogota[/]\n"
        "[dim]Generando lat/lon para los 663 TIDs del dataset de velocidades[/]",
        border_style="bright_blue"
    ))

    # 1. Extraer segmentos unicos
    seg = cargar_segmentos()

    # 2. Geocodificar (o cargar desde cache)
    seg_geo = geocodificar_segmentos(seg)

    # 3. Estadisticas
    imprimir_estadisticas(seg_geo)

    # 4. Mapa interactivo
    console.print("\n[bold yellow]Generando mapa interactivo...[/]")
    _, n_validos = generar_mapa(seg_geo)
    console.print(f"  [green]OK[/] Mapa con {n_validos} tramos: [cyan]{OUT_MAPA}[/]")

    console.print(Panel.fit(
        f"[bold green]Listo![/]\n"
        f"[dim]Tabla de referencia: {OUT_SEGS}[/]\n"
        f"[dim]Mapa interactivo:    {OUT_MAPA}[/]\n\n"
        "[dim]Para enriquecer el CSV completo con lat/lon:[/]\n"
        "[dim]  import pandas as pd[/]\n"
        "[dim]  df = pd.read_csv('data/Velocidades_Bitcarrier...csv')[/]\n"
        "[dim]  geo = pd.read_csv('data/segmentos_geocodificados.csv')[/]\n"
        "[dim]  df = df.merge(geo[['TID','lat','lon']], on='TID', how='left')[/]",
        border_style="green"
    ))


if __name__ == "__main__":
    main()
