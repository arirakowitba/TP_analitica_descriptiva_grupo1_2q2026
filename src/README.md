# Codigo reutilizable

Funciones y modulos auxiliares usados por los notebooks. Se importan desde los notebooks con `from src import ...` despues de agregar la raiz del repo a `sys.path`.

| Modulo | Contenido |
|---|---|
| `config.py` | Rutas centralizadas, relativas a la raiz del repositorio. |
| `externas.py` | Descarga y snapshot de fuentes externas en `data/raw/externas/` (con fecha y MD5), cargadores estandarizados de cada fuente puntual de BA Data y armado de la tabla del Censo 2022 por comuna. |
| `geo.py` | Conversion de coordenadas planas de CABA a WGS84, parseo de WKT, asignacion de puntos a barrios, distancias y conteos en radio. |
| `usig.py` | Limpieza de direcciones y geocodificacion con USIG, con cache local. Ejecutable: `python -m src.usig`. |
| `features.py` | Barrio oficial, tipo de cambio MEP, precios comparables, flags de rango, variables de entorno y contexto por barrio. |
| `eda.py` | Funciones reutilizables para el EDA con fuentes externas: estilo grafico, estadisticos descriptivos, correlaciones con bootstrap, modelos con errores agrupados y visualizaciones territoriales. |

La logica extensa o repetida debe moverse aca para que los notebooks queden legibles y reproducibles.
