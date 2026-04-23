# Diccionario de Datos: Tablero de Cámaras Salvavidas

Este documento explica en detalle cada una de las columnas presentes en los 3 datasets exportados para la construcción del tablero en Power BI.

---

## 1. `dataset_camaras_mapa.csv` (Dimensión: `Dim_Camaras`)
Esta tabla contiene el registro único de las 85 ubicaciones de cámaras salvavidas y sirve como el catálogo o dimensión principal del modelo. También incluye métricas pre-calculadas para resúmenes rápidos.

| Columna | Tipo de Dato | Descripción |
| :--- | :--- | :--- |
| `id_camara` | Texto | Identificador único de la cámara (ej. DEI-001/CAM-01). Es la llave primaria para cruzar con accidentes. |
| `corredor_principal` | Texto | Nombre de la vía principal donde está instalada la cámara (ej. Av. Boyacá, Autopista Norte). Llave para cruzar con velocidades. |
| `via_secundaria` | Texto | Vía que cruza o sirve de referencia de la ubicación exacta. |
| `latitud` | Decimal | Coordenada geográfica de latitud (Eje Y). |
| `longitud` | Decimal | Coordenada geográfica de longitud (Eje X). |
| `velocidad_maxima` | Entero | Límite de velocidad legal de la vía en ese punto (en km/h). |
| `localidad` | Texto | Localidad de Bogotá a la que pertenece la cámara. |
| `vel_promedio_2019` | Decimal | Velocidad promedio registrada en ese corredor durante el mes de análisis en 2019 (antes de las cámaras). |
| `vel_promedio_2022` | Decimal | Velocidad promedio registrada en ese corredor durante el mes de análisis en 2022 (después de las cámaras). |
| `delta_vel` | Decimal | Diferencia absoluta de velocidad (2022 - 2019). Si es negativo, la velocidad disminuyó. |
| `delta_vel_pct` | Decimal | Diferencia porcentual de la velocidad `(delta_vel / vel_promedio_2019) * 100`. |
| `num_accidentes_2019` | Entero | Cantidad total de accidentes ocurridos a menos de 500 metros de esta cámara en 2019. |
| `num_accidentes_2022` | Entero | Cantidad total de accidentes ocurridos a menos de 500 metros de esta cámara en 2022. |
| `delta_accidentes` | Entero | Diferencia absoluta de accidentes (2022 - 2019). Si es negativo, hubo menos accidentes. |
| `acc_con_heridos_2019/2022` | Entero | Número de accidentes catalogados "Con Heridos" cerca de la cámara para los respectivos años. |
| `acc_con_muertos_2019/2022` | Entero | Número de accidentes catalogados "Con Muertos" cerca de la cámara para los respectivos años. |
| `acc_solo_danos_2019/2022` | Entero | Número de accidentes catalogados "Solo Daños" (choques simples) cerca de la cámara para los respectivos años. |
| `match_2019` / `match_2022` | Booleano | Indica si el cruce espacial logró encontrar datos de velocidad válidos a menos de 500m de esta cámara en ese año (True/False). |

---

## 2. `dataset_accidentes_cerca_camaras_mapa.csv` (Hechos: `Fact_Accidentes`)
Registro detallado de los 817 accidentes ocurridos en el radio de influencia (500 metros) de alguna cámara, durante los meses analizados de 2019 y 2022.

| Columna | Tipo de Dato | Descripción |
| :--- | :--- | :--- |
| `Codigo_Accidente` | Texto | Identificador único del siniestro asignado por la Secretaría de Movilidad. |
| `Latitud` / `Longitud` | Decimal | Coordenadas exactas donde ocurrió el accidente. |
| `Hora_Acc` | Entero | Hora en formato militar (0 a 23) en la que ocurrió el siniestro. |
| `Dia_Semana_Acc` | Texto | Día de la semana en que ocurrió el siniestro (Lunes a Domingo). |
| `Clase_Acc` | Texto | Clasificación del tipo de siniestro (Choque, Atropello, Volcamiento, etc.). |
| `Gravedad_Indicador_Tradicional` | Texto | Clasificación de severidad: "Solo Daños", "Con Heridos", "Con Muertos". |
| `Localidad` | Texto | Localidad oficial donde ocurrió el accidente. |
| `corredor_camara` | Texto | Nombre del corredor principal correspondiente a la cámara que capturó el accidente (Llave de agrupamiento). |
| `id_camara_cercana` | Texto | ID de la cámara ubicada a menos de 500m de este accidente. **(Llave foránea hacia `Dim_Camaras`)**. |
| `dist_camara_m` | Decimal | Distancia exacta en metros entre el punto del accidente y la ubicación de la cámara. |
| `anio` | Entero | Año de ocurrencia del accidente (2019 o 2022). |

---

## 3. `dataset_velocidades_horario_camaras.csv` (Hechos: `Fact_Velocidades`)
Contiene los perfiles de velocidad agregados por hora del día. Permite visualizar curvas de congestión.

| Columna | Tipo de Dato | Descripción |
| :--- | :--- | :--- |
| `TID` | Texto | Identificador único del segmento de vía (Tramo) según Waze/Movilidad. |
| `hora` | Entero | Hora del día en formato militar (0 a 23). |
| `vel_promedio_hora` | Decimal | Velocidad promedio de los vehículos en ese tramo de vía durante esa hora específica (en km/h). |
| `corredor_principal` | Texto | Corredor de cámara al que pertenece este segmento de vía (ej. Av. NQS). **(Llave foránea hacia `Dim_Camaras`)**. |
| `anio` | Entero | Año de captura de la información (2019 o 2022). Sirve para comparar líneas de tiempo. |
