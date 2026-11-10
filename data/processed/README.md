# Datos procesados

Esta carpeta conserva dependencias entre etapas y salidas finales. Ejecutar los notebooks 01–16 en orden para regenerarlas desde snapshots locales y cache USIG. No editar los CSV a mano.

Las bases preprocesadas alimentan el tratamiento de nulos; las bases post-ajustes alimentan outliers; el consolidado con flags alimenta descripción y enriquecimiento. La base enriquecida, KPIs, scores, asignaciones, reportes y mart sostienen los resultados finales.

Ver `docs/depuracion_datos.md` y `docs/processed_retirados.json` para copias retiradas, motivos y dependencias. Las exportaciones innecesarias también se eliminaron del código; no se recrean al ejecutar la cadena final. Los reportes conservan evidencia de calidad y análisis, sin replicar datasets completos.
