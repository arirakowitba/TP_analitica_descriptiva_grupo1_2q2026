# Cierre y trazabilidad de PE3

**Estado final al 5 de noviembre de 2026.** La secuencia 01–16 está ejecutada, el paquete local es instalable, los outputs analíticos están embebidos y el dashboard de Power BI está publicado. Este documento conserva las decisiones de PE3 y su estado final; el README contiene la narrativa ejecutiva.

## Acuerdos metodológicos aplicados

- No mezclar unidades, fuentes ni modalidades sin declarar comparabilidad y grano.
- Distinguir oferta publicada, stock censal, contratos, demanda y transacciones.
- Reportar magnitud, incertidumbre, dirección, soporte y limitaciones; no decidir solo por p-valores.
- Tratar “sin evidencia suficiente” como distinto de “efecto inexistente”.
- No convertir asociaciones transversales en efectos causales ni en desplazamiento de alquiler permanente.
- No usar clusters, componentes o factores como índices normativos sin estabilidad y valor incremental.
- Conservar resultados negativos, escenarios no estimables y sensibilidades que cambian la conclusión.

## Secuencia PE3 y decisiones finales

| Notebook | Aporte | Decisión final |
|---|---|---|
| 09 | Cierre del EDA, jerarquía de KPIs y señales comunales | Las señales se muestran separadas; la regla conjunta no se usa como ranking normativo. |
| 10 | PCA y MCA territorial | Representaciones exploratorias sin precios activos; no constituyen índices oficiales. |
| 11 | K-means y Ward | Los clusters describen perfiles, pero su estabilidad es moderada y no reemplazan comuna. |
| 12 | Modelos log-lineales de precio | H3 se interpreta como asociación observacional; venta pierde estabilidad en algunas sensibilidades. |
| 13 | Perfiles de publicaciones y operación | La referencia es la permutación condicionada por fuente × barrio; no se afirma una tipología natural. |
| 14 | MCA de propiedades y análisis factorial barrial | La adecuación permite explorar un factor, no certificar un índice habitacional. |
| 15 | Mart dimensional para Power BI | Granularidades separadas, relaciones 1:N y métricas no aditivas documentadas. |
| 16 | Validación transversal | Centralidad, espacio, multiplicidad, umbrales, factores, clusters y H3 quedan auditados. |

## Resultado por hipótesis

- **H1:** asociación positiva y robusta entre densidad cultural/gastronómica y concentración Airbnb; conserva dependencia espacial y no se interpreta causalmente.
- **H2a:** evidencia insuficiente con tamaño medio del hogar como proxy; no se usa para priorizar.
- **H2b:** evidencia parcial, concentrada en cultura; educación y espacios verdes no muestran apoyo concluyente.
- **H3:** la dirección esperada no se confirma. La asociación estimada es pequeña, contraria y sensible en venta; hay problemas de especificación.
- **H4:** Airbnb coexiste con precios altos, pero también con mayor —no menor— disponibilidad permanente publicada; no prueba sustitución.

## Dashboard

El mart del notebook 15 alimenta un informe público de seis páginas con filtros por operación, fuente y territorio. El recorrido, los hallazgos y la relación con H1–H4 se documentan en la sección 8 del README. El generador conserva el enlace público al regenerar `data/processed/dashboard_mart/powerbi/README.md`.

## Validación final

- Ejecución secuencial aislada de 01–16: **202 celdas de código, 178 imágenes PNG y 0 outputs de error**.
- Once pruebas automatizadas aprobadas y `pip check` sin dependencias incompatibles.
- Los notebooks 04 y 08 eliminan avisos evitables: el diagnóstico multivariado registra un fallback numérico y el resumen territorial usa tipos compatibles con pandas.
- Los datos crudos no se modifican. Las tablas y figuras derivadas permanecen en `data/processed/` y `data/processed/reports/`.

## Evidencia auditable

- Protocolo inferencial: [`protocolo_robustez_pe3.md`](protocolo_robustez_pe3.md).
- Modelo dimensional: [`modelo_data_warehouse_dashboard.md`](modelo_data_warehouse_dashboard.md).
- Matriz final: `data/processed/reports/robustez_pe3/matriz_evidencia_v2.csv`.
- Ejecución: `python -m src.run_notebooks_sequential`.
