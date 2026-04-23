# Data Jam – Velocidad, siniestralidad y cámaras salvavidas en Bogotá D.C.

## Creadores del proyecto

- **Matias Felipe Gonzalez Valencia** — Ingeniería de Sistemas — Pontificia Universidad Javeriana  
- **Sergio Asencio Rodriguez** — Ingeniería de Sistemas — Pontificia Universidad Javeriana  
- **Brayan Nicolas Sarmiento Merchan** — Ingeniería de Sistemas -- Ciencia de Datos — Pontificia Universidad Javeriana

## Descripción
Este proyecto analiza la relación entre la velocidad promedio de circulación, los siniestros viales y la ubicación de cámaras salvavidas en Bogotá D.C., comparando 2019 y 2022.

El problema central es:

> En Bogotá D.C., la velocidad de circulación y los siniestros viales presentan variaciones entre corredores y momentos del día. En este contexto, y considerando la instalación de cámaras salvavidas en distintos puntos de la ciudad entre 2019 y 2020, resulta relevante analizar si en estos corredores se observan cambios en la velocidad promedio de circulación y en el comportamiento de los siniestros viales antes y después de su implementación.

## Pregunta de análisis
¿Qué cambios se observan en la velocidad promedio de circulación y en el comportamiento de los siniestros viales en los corredores de Bogotá D.C. donde se instalaron cámaras salvavidas, al comparar 2019 y 2022?

## Fuentes de datos
Se utilizaron tres fuentes públicas:

- **Velocidad promedio por corredor vial**  
  Secretaría Distrital de Movilidad  
  https://datos.movilidadbogota.gov.co/datasets/313488d6e74948f1bd06c3eccca7207c_0/explore?location=0.001635%2C0.000000%2C1.00

- **Anuario de siniestralidad vial**  
  Datos Abiertos Bogotá  
  https://datosabiertos.bogota.gov.co/dataset/anuario-siniestralidad/resource/35168f38-f3b3-4411-a0c5-545f3ec8869e

- **Cámaras salvavidas Bogotá D.C.**  
  Datos Abiertos Bogotá  
  https://datosabiertos.bogota.gov.co/dataset/camaras-salvavidas-bogota-d-c

## Metodología
El análisis se desarrolló en cuatro pasos:

1. Descarga y revisión de los datasets.
2. Limpieza y estandarización de siniestralidad, cámaras y velocidades.
3. Integración espacial y temporal de las tres fuentes.
4. Construcción de tablas, gráficos comparativos y tablero en Power BI.

Se compararon **octubre de 2019** y **octubre de 2022**, porque fueron los periodos con datos más accesibles y comparables. No se incluyeron años de pandemia por sus cambios atípicos en la movilidad.

## Principales hallazgos
- Los cambios de velocidad entre 2019 y 2022 no fueron iguales en todos los corredores.
- La accidentalidad se concentra más en horas de alta exposición vial que en momentos de velocidad máxima.
- No se observa una relación lineal simple entre mayor velocidad y mayor número de accidentes.
- En 2022 se observan cambios en velocidad y accidentalidad frente a 2019, pero estos no pueden interpretarse como causalidad directa del efecto de las cámaras.

## Herramientas
- Python
- Power BI
- Excel

Librerías principales:
- pandas
- numpy
- geopandas
- scipy
- matplotlib
- seaborn

## Cómo ejecutar el proyecto
