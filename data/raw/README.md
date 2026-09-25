# Datos crudos

Esta carpeta contiene los archivos obtenidos por scraping o descarga directa. Deben conservarse sin modificaciones manuales para mantener trazabilidad entre fuente, extraccion, limpieza y analisis.

## Contenido

| Carpeta | Fuente | Descripcion |
|---|---|---|
| `airbnb/` | Airbnb | Bases de alquiler temporario en CABA, con series corta y mensual, archivos normalizados, listings completos y amenities en formato largo. |
| `mercadolibre_inmuebles_ventas/` | Mercado Libre | Publicaciones de inmuebles en venta en CABA. |
| `mercadolibre_inmuebles_alquiler/` | Mercado Libre | Publicaciones de alquiler permanente en CABA. |
| `mercadolibre_inmuebles_alquiler temporario/` | Mercado Libre | Publicaciones de alquiler temporario en CABA. |
| `argenprop/` | ArgenProp | Publicaciones relevadas de ArgenProp y archivos de diagnostico. |
| `zonaprop/` | ZonaProp | Publicaciones relevadas de ZonaProp. |

## Reglas de uso

- No editar estos archivos manualmente.
- No imputar, filtrar ni normalizar sobre los CSV crudos.
- Guardar cualquier salida limpia, consolidada o enriquecida en `data/processed`.
- Documentar en notebooks o en `docs/` toda decision de limpieza que afecte registros, columnas, tipos, unidades o categorias.
