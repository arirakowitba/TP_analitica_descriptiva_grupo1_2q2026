# Codigo reutilizable

Funciones y modulos auxiliares usados por los notebooks. Desde la raíz del repositorio, ejecutar `python -m pip install -r requirements.txt` para instalar el proyecto en modo editable. Luego se importan con `from src import ...` desde cualquier directorio, usando el mismo entorno de Python. Las dependencias se declaran en `pyproject.toml`; `src` es el paquete local y no debe instalarse desde PyPI.

| Modulo | Contenido |
|---|---|
| `config.py` | Rutas centralizadas, relativas a la raiz del repositorio. |
| `externas.py` | Descarga y snapshot de fuentes externas en `data/raw/externas/` (con fecha y MD5), cargadores estandarizados de cada fuente puntual de BA Data y armado de la tabla del Censo 2022 por comuna. |
| `geo.py` | Conversion de coordenadas planas de CABA a WGS84, parseo de WKT, asignacion de puntos a barrios, distancias y conteos en radio. |
| `usig.py` | Limpieza de direcciones y geocodificacion con USIG, con cache local. Ejecutable: `python -m src.usig`. |
| `features.py` | Barrio oficial, tipo de cambio MEP, precios comparables, flags de rango, variables de entorno y contexto por barrio. |
| `eda.py` | Funciones reutilizables para el EDA con fuentes externas: estilo grafico, estadisticos descriptivos, correlaciones con bootstrap, modelos con errores agrupados y visualizaciones territoriales. |

La logica extensa o repetida debe moverse aca para que los notebooks queden legibles y reproducibles.
