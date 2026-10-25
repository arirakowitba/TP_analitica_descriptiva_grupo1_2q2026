# Importar el mart en Power BI

## Archivos
- Los CSV de la carpeta raíz son las tablas del modelo; cada archivo es una tabla.
- relaciones.csv enumera relaciones 1:* con filtro unidireccional.
- esquema_powerbi.json contiene columnas y tipos sugeridos.
- medidas_dax.dax ofrece medidas iniciales; fnLoadMartCsv.m es una función de carga opcional.
- data_model.json documenta fuentes, granos, conteos y reglas metodológicas.

## Carga recomendada
1. Descomprimir el paquete y usar Obtener datos → Texto/CSV para cargar cada CSV de la carpeta raíz. No cargar los archivos dentro de powerbi/ como tablas del modelo.
2. Revisar tipos con esquema_powerbi.json: claves enteras, fechas como fecha y métricas como decimal; mantener identificadores y categorías como texto.
3. En Vista Modelo, crear únicamente las relaciones listadas en relaciones.csv (1:* y dirección Single). No relacionar hechos entre sí.
4. Ocultar claves técnicas en la vista de informe. Mantener dimensiones visibles para segmentadores.
5. Incorporar las medidas necesarias desde medidas_dax.dax y comprobarlas con filtros territoriales y de operación.

## Reglas para interpretar
- fact_publicacion es una fila por publicación capturada; la extracción es un corte, no una serie de snapshots.
- Precios, medianas, ratios, densidades y porcentajes no son aditivos. Usar la métrica validada al grano de barrio o comuna, o recalcular numerador y denominador compatibles.
- El Censo 2022 está a nivel comuna. tamano_medio_hogar es un proxy para H2a, no mide adecuación habitacional individual.
- La jerarquía comuna a barrio está normalizada. En hechos de publicaciones, comuna se deriva desde barrio para evitar rutas de filtro ambiguas; filas sin barrio oficial no se asignan a una comuna mediante inferencia.
- Los conteos describen oferta publicada y cobertura de fuentes; no equivalen a stock residencial, contratos ni transacciones.
