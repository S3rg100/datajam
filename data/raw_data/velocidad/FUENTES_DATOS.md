# Fuentes de Datos - Velocidades Bitcarrier

Los siguientes archivos deben descargarse manualmente desde el portal de datos abiertos de la Secretaría de Movilidad de Bogotá, ya que exceden el límite de tamaño de GitHub (~300 MB cada uno).

## Velocidades Octubre 2019

- **URL:** [https://datos.movilidadbogota.gov.co/datasets/313488d6e74948f1bd06c3eccca7207c_0/explore](https://datos.movilidadbogota.gov.co/datasets/313488d6e74948f1bd06c3eccca7207c_0/explore?location=0.001635%2C0.000000%2C1.00)
- **Nombre esperado del archivo:** `Velocidades_Bitcarrier_Octubre_2019_7909733598528545915.csv`
- **Tamaño aproximado:** 327 MB
- **Descripción:** Registros de velocidad vehicular por segmento de vía (TID) cada 15 minutos durante octubre de 2019, capturados por sensores Bitcarrier.

## Velocidades Octubre 2022

- **URL:** [https://datos.movilidadbogota.gov.co/datasets/efcb0eda33d04a3f984ae60ac5704799_0/explore](https://datos.movilidadbogota.gov.co/datasets/efcb0eda33d04a3f984ae60ac5704799_0/explore?location=0.001635%2C0.000000%2C1.00)
- **Nombre esperado del archivo:** `Velocidades_Bitcarrier_Octubre_2022_5740524589707522675.csv`
- **Tamaño aproximado:** 307 MB
- **Descripción:** Registros de velocidad vehicular por segmento de vía (TID) cada 15 minutos durante octubre de 2022, capturados por sensores Bitcarrier.

## Instrucciones

1. Acceda a cada URL y haga clic en el botón de **Descarga** (formato CSV).
2. Renombre los archivos descargados exactamente como se indica arriba.
3. Coloque ambos archivos en esta misma carpeta (`data/raw_data/velocidad/`).
4. Una vez colocados, puede ejecutar el pipeline de limpieza con `python main.py`.
