# -*- coding: utf-8 -*-
"""
=============================================================================
  MAIN - Pipeline de Análisis: Cámaras Salvavidas Bogotá
=============================================================================
  Orquesta la ejecución de todos los scripts del proyecto en orden.

  PREREQUISITOS:
    - Los datos crudos de velocidad deben estar descargados en:
        data/raw_data/velocidad/
      (ver FUENTES_DATOS.md en esa carpeta)
    - Los datos crudos de siniestralidad deben estar en:
        data/raw_data/Siniestralidad/DataJamSiniestralidad.csv
    - Los datos crudos de cámaras (shapefile) deben estar en:
        data/raw_data/camaras_salvavidas/

  USO:
    python scripts/main.py              # Ejecuta solo el pipeline de análisis
                                         (asume que los datos limpios ya existen)
    python scripts/main.py --todo       # Ejecuta limpieza + análisis completo

  PASOS:
    Fase 1 (Limpieza - solo con --todo):
      1.1  Limpieza de siniestralidad
      1.2  Construcción tabla de cámaras desde shapefile
      1.3  Limpieza de cámaras

    Fase 2 (Análisis - siempre):
      2.1  Cruce siniestralidad × velocidades (2019 y 2022)
      2.2  Análisis de impacto de cámaras salvavidas
      2.3  Generación de datasets para Power BI + mapa interactivo
=============================================================================
"""

import sys
import subprocess
import time
from pathlib import Path

# ── Configuración ─────────────────────────────────────────────────────────────
# BASE_DIR apunta a la raíz del proyecto (datajam/), un nivel arriba de scripts/
BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS  = BASE_DIR / "scripts"

# Colores para consola
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def ejecutar_script(nombre: str, ruta: Path) -> bool:
    """Ejecuta un script Python como subproceso y reporta el resultado."""
    print(f"\n{'='*70}")
    print(f"  {CYAN}{BOLD}{nombre}{RESET}")
    print(f"  {ruta.relative_to(BASE_DIR)}")
    print(f"{'='*70}")

    if not ruta.exists():
        print(f"  {RED}[ERROR] Archivo no encontrado: {ruta}{RESET}")
        return False

    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(ruta)],
            cwd=str(BASE_DIR),
            env={**__import__('os').environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=False,
            text=True,
        )
        elapsed = time.time() - t0

        if result.returncode == 0:
            print(f"\n  {GREEN}[OK] Completado en {elapsed:.1f}s{RESET}")
            return True
        else:
            print(f"\n  {RED}[FALLO] Exit code: {result.returncode} ({elapsed:.1f}s){RESET}")
            return False

    except Exception as e:
        print(f"\n  {RED}[ERROR] {e}{RESET}")
        return False


def verificar_datos_limpios() -> list[str]:
    """Verifica que los datos limpios necesarios existan."""
    archivos_requeridos = [
        ("Siniestralidad limpia",
         BASE_DIR / "data" / "cleaned_data" / "Siniestralidad" / "siniestralidad_clean.csv"),
        ("Velocidades 2019 limpias",
         BASE_DIR / "data" / "cleaned_data" / "velocidades" / "velocidades_2019_final.csv"),
        ("Velocidades 2022 limpias",
         BASE_DIR / "data" / "cleaned_data" / "velocidades" / "velocidades_2022_final.csv"),
        ("Cámaras salvavidas limpias",
         BASE_DIR / "data" / "cleaned_data" / "camaras_salvavidas" / "tabla_camaras_salvavidas_clean.csv"),
    ]

    faltantes = []
    for nombre, ruta in archivos_requeridos:
        if ruta.exists():
            size_mb = ruta.stat().st_size / 1024 / 1024
            print(f"  {GREEN}[OK]{RESET} {nombre} ({size_mb:.1f} MB)")
        else:
            print(f"  {RED}[FALTA]{RESET} {nombre}")
            print(f"         {ruta}")
            faltantes.append(nombre)

    return faltantes


def main():
    modo_todo = "--todo" in sys.argv

    print(f"\n{'#'*70}")
    print(f"  {BOLD}{CYAN}PIPELINE DE ANÁLISIS - CÁMARAS SALVAVIDAS BOGOTÁ{RESET}")
    print(f"  Modo: {'COMPLETO (limpieza + análisis)' if modo_todo else 'ANÁLISIS (datos limpios requeridos)'}")
    print(f"{'#'*70}")

    resultados = []
    t_total = time.time()

    # ══════════════════════════════════════════════════════════════════════════
    #  FASE 1: LIMPIEZA (solo con --todo)
    # ══════════════════════════════════════════════════════════════════════════
    if modo_todo:
        print(f"\n{BOLD}{YELLOW}═══ FASE 1: LIMPIEZA DE DATOS ═══{RESET}")

        pasos_limpieza = [
            ("1.1 Limpieza de Siniestralidad",
             SCRIPTS / "Siniestralidad" / "LimpiezaSiniestralidad.py"),
            ("1.2 Construcción Tabla de Cámaras (Shapefile → CSV)",
             SCRIPTS / "camaras_salvavidas" / "01_construir_tabla_camaras.py"),
            ("1.3 Limpieza de Cámaras Salvavidas",
             SCRIPTS / "camaras_salvavidas" / "02_limpieza_camaras.py"),
            ("1.4 Resumen de Cámaras Salvavidas",
             SCRIPTS / "camaras_salvavidas" / "03_resumen_camaras.py"),
        ]

        for nombre, ruta in pasos_limpieza:
            ok = ejecutar_script(nombre, ruta)
            resultados.append((nombre, ok))
            if not ok:
                print(f"\n{RED}{BOLD}Pipeline interrumpido en: {nombre}{RESET}")
                print("Corrija el error y vuelva a ejecutar.")
                sys.exit(1)

    # ══════════════════════════════════════════════════════════════════════════
    #  VERIFICACIÓN DE DATOS LIMPIOS
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{BOLD}{YELLOW}═══ VERIFICACIÓN DE DATOS LIMPIOS ═══{RESET}\n")
    faltantes = verificar_datos_limpios()

    if faltantes:
        print(f"\n{RED}{BOLD}Faltan {len(faltantes)} archivo(s) de datos limpios.{RESET}")
        print(f"Ejecute '{CYAN}python main.py --todo{RESET}' para correr el pipeline completo")
        print(f"o coloque los archivos faltantes manualmente.")
        sys.exit(1)

    # ══════════════════════════════════════════════════════════════════════════
    #  FASE 2: ANÁLISIS
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{BOLD}{YELLOW}═══ FASE 2: ANÁLISIS Y GENERACIÓN DE RESULTADOS ═══{RESET}")

    pasos_analisis = [
        ("2.1 Cruce Siniestralidad × Velocidades (2019 y 2022)",
         SCRIPTS / "cruce_siniestralidad_velocidades.py"),
        ("2.2 Análisis de Impacto de Cámaras Salvavidas",
         SCRIPTS / "analisis_camaras_salvavidas.py"),
        ("2.3 Generación de Datasets para Power BI + Mapa Interactivo",
         SCRIPTS / "mapa_camaras_salvavidas.py"),
    ]

    for nombre, ruta in pasos_analisis:
        ok = ejecutar_script(nombre, ruta)
        resultados.append((nombre, ok))
        if not ok:
            print(f"\n{RED}{BOLD}Pipeline interrumpido en: {nombre}{RESET}")
            print("Corrija el error y vuelva a ejecutar.")
            sys.exit(1)

    # ══════════════════════════════════════════════════════════════════════════
    #  RESUMEN FINAL
    # ══════════════════════════════════════════════════════════════════════════
    elapsed = time.time() - t_total

    print(f"\n{'#'*70}")
    print(f"  {GREEN}{BOLD}PIPELINE COMPLETADO EXITOSAMENTE{RESET}  ({elapsed:.1f}s)")
    print(f"{'#'*70}")
    print(f"\n  Pasos ejecutados:")
    for nombre, ok in resultados:
        estado = f"{GREEN}OK{RESET}" if ok else f"{RED}FALLO{RESET}"
        print(f"    [{estado}] {nombre}")

    print(f"\n  {BOLD}Archivos de salida:{RESET}")
    print(f"    Tablas:    outputs/tables/")
    print(f"    Figuras:   outputs/figures/")
    print(f"    Power BI:  data/processed_data/camaras_salvavidas/dataset_*.csv")
    print(f"    Mapa HTML: outputs/figures/camaras_salvavidas/mapa_camaras_salvavidas.html")
    print()


if __name__ == "__main__":
    main()
