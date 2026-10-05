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
8. `08_eda_con_fuentes_externas.ipynb`: primeros cruces exploratorios con fuentes externas.

Los notebooks usan rutas relativas al repositorio y guardan datasets limpios, consolidados o reportes tecnicos en `data/processed`. La logica reutilizable de los notebooks 06 y 07 esta en `src/`.

El notebook 06 lee las fuentes externas desde `data/raw/externas/` y la geocodificacion desde `data/processed/geocodificacion_usig_cache.csv`; con ambos presentes no hace llamadas de red. Para regenerar la cache desde cero: `python -m src.usig` (aprox. 25 minutos).
