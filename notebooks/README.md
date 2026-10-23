# Notebooks

Esta carpeta reune los notebooks de la PreEntrega 2 y etapas posteriores. El criterio es separar responsabilidades para que la cadena de trabajo sea trazable y facil de revisar.

Orden de ejecucion:

1. `01_perfilado_calidad_raw.ipynb`: inventario de archivos crudos, columnas, tipos de datos, nulos iniciales, cardinalidad, rangos y duplicados.
2. `02_normalizacion_y_limpieza.ipynb`: normalizacion de textos, categorias, barrios, monedas, operaciones, fechas y construccion de datasets preprocesados.
3. `03_analisis_de_nulos_con_tests_hipotesis.ipynb`: flags de nulidad, matrices faltante-vs-faltante, faltante-vs-cuantitativas y faltantes por label categorico.
4. `04_outliers.ipynb`: deteccion de valores imposibles y valores extremos mediante flags, sin eliminacion automatica de casos plausibles.
5. `05_feature_engineering_y_eda_inicial.ipynb`: EDA inicial sobre la base consolidada, sin fuentes externas.
6. `06_fuentes_externas.ipynb`: snapshot e inventario de fuentes externas, Censo 2022 por comuna, geocodificacion USIG, barrio y comuna oficiales, contexto urbano por barrio y compatibilidad con la unidad de analisis.
7. `07_feature_engineering.ipynb`: alcance, normalizacion monetaria (dolar MEP), precios comparables, entorno urbano por publicacion, KPIs por barrio y por comuna, diccionario de variables derivadas.
8. `08_eda_con_fuentes_externas.ipynb`: EDA con la base enriquecida: distribución territorial de las operaciones, precios y tipologías, servicios y demografía, evidencia preliminar para H1, H2a, H2b, H3 y H4, y síntesis de hallazgos, limitaciones y próximos pasos.

Los notebooks usan rutas relativas al repositorio y guardan datasets limpios, consolidados o reportes tecnicos en `data/processed`. La logica reutilizable de los notebooks 06 y 07 esta en `src/`.

El notebook 06 lee las fuentes externas desde `data/raw/externas/` y la geocodificacion desde `data/processed/geocodificacion_usig_cache.csv`; con ambos presentes no hace llamadas de red. Para regenerar la cache desde cero: `python -m src.usig` (aprox. 25 minutos).

## Continuación: PreEntrega 3

La secuencia propuesta parte de la base enriquecida y de los KPIs generados por 07 y 08. Cada notebook lee las salidas versionadas del anterior o los mismos insumos estables de la etapa previa; no vuelve a ejecutar limpieza ni enriquecimiento.

9. `09_cierre_eda_y_priorizacion_kpis.ipynb`: recupera los resultados de 08, jerarquiza KPIs por decisión y construye una señal exploratoria y transparente para localizar comunas que ameritan un diagnóstico adicional.
10. `10_reduccion_dimensionalidad_perfiles.ipynb`: estandariza servicios y transporte por barrio exportados por 09; aplica PCA y MCA como representaciones exploratorias y exporta coordenadas y cargas.
11. `11_segmentacion_y_validacion.ipynb`: compara clustering jerárquico y K-means sobre los componentes de PCA; revisa silueta, estabilidad por submuestras e interpretación de perfiles. Los grupos no se interpretan como tipologías definitivas.
12. `12_modelos_explicativos_precios.ipynb`: estima modelos log-lineales separados para venta y alquiler, compara especificaciones con y sin controles por fuente y reporta asociaciones con incertidumbre agrupada por barrio. No se usa como modelo causal ni como pronóstico.
13. `13_correspondencia_operacion_perfiles_propiedades.ipynb`: valida si las etiquetas preexistentes (venta, alquiler permanente y temporal) se asocian con clusters no supervisados de atributos comparables de propiedad y entorno. Fija k=3 por la pregunta externa, excluye operación/fuente/precio del espacio, contrasta AMI mediante permutaciones dentro de fuente × barrio (con sensibilidad condicionada solo por fuente) y perfila precios después por modalidad. Cada bloque explicita supuestos y límites; no busca crear nuevas tipologías.

**Orden:** ejecutar 01–08 y luego 09–13. El notebook 13 parte de la base enriquecida estable generada en 07 y agrega un análisis complementario a la segmentación territorial de 10–11; no usa etiquetas de cluster previas como insumo. Los notebooks PE3 son un primer desarrollo: deben revisarse variables, cobertura y resultados reales con el equipo. El dashboard queda fuera de esta secuencia. Las ejecuciones finales deben conservar outputs visibles y producir salidas en `data/processed/` o `data/processed/reports/`.


14. `14_mca_y_analisis_factorial.ipynb`: MCA de propiedades con etiquetas suplementarias y análisis factorial barrial condicionado a pruebas de adecuación.
15. `15_modelo_data_warehouse_dashboard.ipynb`: ejecución del mart dimensional para consumo del dashboard.

Los notebooks 14–15 se ejecutan después del 13. El notebook 15 genera `data/processed/dashboard_mart/`; consultar `docs/modelo_data_warehouse_dashboard.md` para granularidades, relaciones y reglas de agregación. El notebook 14 recupera los cuadrados de coausencia del notebook 03 como advertencia sobre patrones de carga/cobertura, no como factores de mercado.