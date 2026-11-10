# Cadena de análisis

Ejecutar desde la raíz: `python -m src.run_notebooks_sequential`. La instalación editable de `requirements.txt` hace disponible el paquete local `src` desde cualquier notebook. El ejecutor guarda outputs y se detiene ante el primer error.

Orden: 01 perfilado; 02 limpieza; 03 nulos; 04 outliers; 05 descripción; 06 fuentes externas; 07 variables y KPIs; 08 hipótesis; 09 listas operativas; 10 PCA; 11 segmentación; 12 modelos de precio; 13 correspondencia de propiedades/operación; 14 diagnósticos complementarios; 15 mart; 16 validación transversal.

Los notebooks 13–14 son anexos metodológicos: no alimentan una decisión adicional. Los resultados que informan acciones y sus límites se consolidan en el README raíz. Las conclusiones se escriben en Markdown junto a los resultados; tablas y gráficos se recalculan.

No repetir scraping: 06 usa snapshots externos y la cache USIG versionada. Conservarla para una ejecución sin red. Dependencias entre etapas y depuración: `docs/depuracion_datos.md`. Instrucciones para dashboard: `docs/ajustes_dashboard.md`.
