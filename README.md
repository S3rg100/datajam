# Data Jam – Velocidad, siniestralidad y cámaras salvavidas en Bogotá D.C.

## Creadores del proyecto

- **Matias Felipe Gonzalez Valencia** — Ingeniería de Sistemas — Pontificia Universidad Javeriana
- **Sergio Asencio Rodriguez** — Ingeniería de Sistemas — Pontificia Universidad Javeriana
- **Brayan Nicolas Sarmiento Merchan** — Ingeniería de Sistemas – Ciencia de Datos — Pontificia Universidad Javeriana

## Descripción

Este proyecto analiza la relación entre la velocidad promedio de circulación, los siniestros viales y la ubicación de cámaras salvavidas en Bogotá D.C., comparando octubre de 2019 (pre-cámaras) y octubre de 2022 (post-cámaras).

El problema central es:

> En Bogotá D.C., la velocidad de circulación y los siniestros viales presentan variaciones entre corredores y momentos del día. En este contexto, y considerando la instalación de **92 cámaras salvavidas** en distintos puntos de la ciudad entre 2019 y 2020, resulta relevante analizar si en estos corredores se observan cambios en la **velocidad promedio de circulación** y en el **comportamiento de los siniestros viales** antes y después de su implementación.

## Pregunta de análisis

¿Qué cambios se observan en la velocidad promedio de circulación y en el comportamiento de los siniestros viales en los corredores de Bogotá D.C. donde se instalaron cámaras salvavidas, al comparar 2019 y 2022?

## Fuentes de datos

| Dataset                     | Fuente                                                                                                                                    | Periodo             | Registros |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | --------- |
| Velocidades Bitcarrier 2019 | [Datos Abiertos Movilidad Bogotá](https://datos.movilidadbogota.gov.co/datasets/313488d6e74948f1bd06c3eccca7207c_0/explore)               | Octubre 2019        | ~3.2M     |
| Velocidades Bitcarrier 2022 | [Datos Abiertos Movilidad Bogotá](https://datos.movilidadbogota.gov.co/datasets/efcb0eda33d04a3f984ae60ac5704799_0/explore)               | Octubre 2022        | ~2.8M     |
| Siniestralidad Vial         | [Datos Abiertos Bogotá](https://datosabiertos.bogota.gov.co/dataset/anuario-siniestralidad/resource/35168f38-f3b3-4411-a0c5-545f3ec8869e) | Oct 2019 y Oct 2022 | 4,334     |
| Cámaras Salvavidas          | [Datos Abiertos Bogotá](https://datosabiertos.bogota.gov.co/dataset/camaras-salvavidas-bogota-d-c) (Shapefile)                            | 2019-2020           | 92        |

> **Nota:** Los archivos de velocidades (~300 MB cada uno) no se incluyen en este repositorio por su tamaño. Consulte `data/raw_data/velocidad/FUENTES_DATOS.md` para instrucciones de descarga.

## Metodología

El análisis se desarrolló en cuatro pasos:

### 1. Descarga y revisión de los datasets

Se obtuvieron los datos desde las fuentes públicas listadas arriba. Se compararon **octubre de 2019** y **octubre de 2022** porque fueron los periodos con datos más accesibles y comparables. No se incluyeron años de pandemia por sus cambios atípicos en la movilidad.

### 2. Limpieza y estandarización

- **Siniestralidad:** Filtrado por octubre 2019/2022, normalización de texto, codificación de variables booleanas.
- **Velocidades:** Eliminación de columnas nulas, parseo de fechas, eliminación de velocidades imposibles (>150 km/h), deduplicación, geocodificación de segmentos viales (TID) mediante Nominatim/OpenStreetMap.
- **Cámaras:** Extracción de coordenadas desde shapefile, limpieza de nombres de corredores.

### 3. Integración espacial y temporal

- **KDTree (scipy):** Asociación de accidentes al segmento de vía más cercano (umbral ≤500m ≈ 0.005°).
- **Agregación horaria:** Velocidades promediadas por hora del día para cada segmento, permitiendo comparar contra la hora del accidente.
- **Cruce cámaras:** Asociación de cada cámara con los TIDs y accidentes dentro de su radio de influencia.

### 4. Análisis comparativo y construcción de tablero

- Velocidad promedio por corredor y hora del día.
- Delta de velocidad (km/h y %) por corredor con cámara.
- Frecuencia y gravedad de accidentes cerca de cámaras.
- Generación de datasets consolidados para visualización en Power BI.

## Principales hallazgos

| Indicador                        | 2019 (Pre-cámara) | 2022 (Post-cámara) | Cambio    |
| -------------------------------- | ----------------- | ------------------ | --------- |
| Accidentes cerca de cámaras      | 566               | 251                | **-56%**  |
| Tasa diaria de accidentes        | 18.3              | 8.1                | -10.2     |
| Vel. promedio corredores cámara  | 29.1 km/h         | 31.2 km/h          | +2.1 km/h |
| Corredores con reducción de vel. | —                 | 5 de 9             | —         |

- Los cambios de velocidad entre 2019 y 2022 no fueron iguales en todos los corredores.
- La accidentalidad se concentra más en horas de alta exposición vial que en momentos de velocidad máxima.
- No se observa una relación lineal simple entre mayor velocidad y mayor número de accidentes.
- En 2022 se observan cambios en velocidad y accidentalidad frente a 2019, pero estos no pueden interpretarse como causalidad directa del efecto de las cámaras.

## Herramientas

- **Python** — Pipeline de datos y análisis
- **Power BI** — Tablero interactivo de resultados
- **Excel** — Revisión exploratoria de datos

Librerías principales: `pandas`, `numpy`, `geopandas`, `scipy`, `matplotlib`, `seaborn`, `folium`

## Cómo ejecutar el proyecto

### Prerrequisitos

- Python 3.10+
- Los datos crudos de velocidad descargados (ver `data/raw_data/velocidad/FUENTES_DATOS.md`)

### Instalación

```bash
cd datajam
pip install -r requirements.txt
```

### Ejecución

**Opción 1: Solo análisis** (si los datos limpios ya existen en `data/cleaned_data/`):

```bash
python scripts/main.py
```

**Opción 2: Pipeline completo** (limpieza de datos + análisis):

```bash
python scripts/main.py --todo
```

El pipeline genera automáticamente:

- Tablas resumen en `outputs/tables/`
- Gráficas comparativas en `outputs/figures/`
- Datasets listos para Power BI en `data/processed_data/camaras_salvavidas/`
- Mapa interactivo HTML en `outputs/figures/camaras_salvavidas/`

## Estructura del Repositorio

```
datajam/
├── data/
│   ├── raw_data/                          # Datos crudos originales
│   │   ├── velocidad/
│   │   │   └── FUENTES_DATOS.md           # URLs de descarga
│   │   ├── Siniestralidad/
│   │   └── camaras_salvavidas/            # Shapefile de cámaras
│   ├── cleaned_data/                      # Datos limpios
│   │   ├── velocidades/                   # CSVs de velocidad limpios + geocodificación
│   │   ├── Siniestralidad/
│   │   └── camaras_salvavidas/
│   └── processed_data/                    # Cruces y datasets finales
│       ├── velocidad y siniestralidad 2019/
│       ├── velocidad y siniestralidad 2022/
│       └── camaras_salvavidas/            # Datasets para Power BI
│
├── scripts/
│   ├── Siniestralidad/
│   │   └── LimpiezaSiniestralidad.py      # Limpieza de datos de accidentes
│   ├── velocidades/
│   │   ├── limpiar_velocidades.py         # Pipeline de limpieza Bitcarrier
│   │   ├── refinar_datasets.py            # Refinamiento y eliminación de redundancia
│   │   ├── geocodificar_segmentos.py      # Geocodificación TIDs 2022 (Nominatim)
│   │   └── geocodificar_2019_faltantes.py # Geocodificación TIDs 2019
│   ├── camaras_salvavidas/
│   │   ├── 01_construir_tabla_camaras.py  # Shapefile → CSV
│   │   ├── 02_limpieza_camaras.py         # Limpieza y normalización
│   │   └── 03_resumen_camaras.py          # Estadísticas descriptivas
│   ├── cruce_siniestralidad_velocidades.py # Cruce espacial accidentes×velocidades
│   ├── analisis_camaras_salvavidas.py      # Comparativa 2019 vs 2022 por cámara
│   ├── mapa_camaras_salvavidas.py          # Mapa interactivo + datasets Power BI
│   └── main.py                             # Orquestador del pipeline completo
│
├── outputs/
│   ├── figures/                           # Gráficas PNG y mapas HTML
│   └── tables/                            # Tablas CSV de resultados
│
├── requirements.txt                       # Dependencias Python
└── README.md                              # Este archivo
```
