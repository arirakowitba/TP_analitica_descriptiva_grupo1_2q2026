# Dependencias y depuración de datos

Se retiran únicamente los archivos de `processed_retirados.json`; cada entrada conserva nombre, tamaño previo y motivo. No se modifica `data/raw/` ni la cache USIG. La lista explícita se puede revisar con `python -m src.depurar_processed`; `--apply` retira solo esos archivos dentro de la raíz de `data/processed/`.

| Productor | Insumo que se conserva | Consumidor |
|---|---|---|
| 02 | Bases preprocesadas por fuente | 03 |
| 03 | Bases por fuente post-ajustes con flags | 04 |
| 04 | Consolidado con outliers/flags | 05, 06 y 07 vía `config.BASE_CONSOLIDADA` |
| 06 | Ubicación, contexto barrial, Censo y cache de geocodificación | 07 y validaciones territoriales |
| 07 | Base enriquecida, KPIs, diccionario de variables | 08–16 y mart |
| 09–14 | Features, scores, asignaciones y reportes de modelos/perfiles | Etapas posteriores y auditoría |
| 15–16 | Mart, paquete Power BI y auditoría final | Dashboard y revisión de resultados |

Se suprimen las exportaciones de snapshots previos a ajustes, las copias individuales con outliers y la consolidación preliminar. El diagnóstico permanece en outputs del notebook y reportes; no requiere una copia completa del dataset. 04 exige las bases post-ajustes y 05 exige el consolidado final: se retiran fallbacks a versiones anteriores para evitar resultados distintos según los archivos disponibles.

Los CSV de reportes se conservan como evidencia de calidad o resultados finales. No se borran archivos por antigüedad o similitud de nombre. El manifiesto enumera 22 copias completas sin consumidor y cinco salidas analíticas reemplazadas, aproximadamente 333 MB decimales antes de retirarlas. La cache, los intermedios realmente consumidos y los outputs analíticos se conservan aunque aumenten el tamaño del repositorio.

La reproducibilidad se comprueba ejecutando 01–16, aplicando la lista de depuración y verificando mart/tests. Los resultados efectivos y cualquier límite de esa comprobación están en `validacion_cierre.md`. La eliminación reduce el checkout actual; los blobs históricos siguen en el historial de Git. No se reescribe ese historial.
