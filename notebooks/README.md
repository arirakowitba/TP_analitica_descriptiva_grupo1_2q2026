# Notebooks

Esta carpeta reune los notebooks de la PreEntrega 2 y etapas posteriores. El criterio es separar responsabilidades para que la cadena de trabajo sea trazable y facil de revisar.

Orden de ejecucion:

1. `01_perfilado_calidad_raw.ipynb`: inventario de archivos crudos, columnas, tipos de datos, nulos iniciales, cardinalidad, rangos y duplicados.
2. `02_normalizacion_y_limpieza.ipynb`: normalizacion de textos, categorias, barrios, monedas, operaciones, fechas y construccion de datasets preprocesados.
3. `03_analisis_de_nulos.ipynb`: flags de nulidad, matrices faltante-vs-faltante, faltante-vs-cuantitativas y faltantes por label categorico.
4. `04_outliers.ipynb`: deteccion de valores imposibles y valores extremos mediante flags, sin eliminacion automatica de casos plausibles.
5. `05_eda_inicial.ipynb`: EDA inicial sobre la base consolidada, sin fuentes externas.
6. `06_fuentes_externas.ipynb`: inventario, carga y evaluacion de compatibilidad de fuentes externas.
7. `07_eda_con_fuentes_externas.ipynb`: primeros cruces exploratorios con fuentes externas.

Los notebooks usan rutas relativas al repositorio y guardan datasets limpios, consolidados o reportes tecnicos en `data/processed`.
