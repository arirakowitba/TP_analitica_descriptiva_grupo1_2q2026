# Documentacion de scrapers

Este documento resume el rol de cada scraper, las fuentes relevadas, las salidas generadas y las limitaciones conocidas. Los archivos crudos se conservan en `data/raw` y no deben modificarse manualmente; cualquier limpieza o consolidacion posterior debe guardarse en `data/processed`.

## Resumen de fuentes

| Fuente | Script principal | Operacion relevada | Salida principal | Estado de cobertura |
|---|---|---|---|---|
| Mercado Libre | `scrappers/scraper_mercadolibre_ventas.py` | Venta | `data/raw/mercadolibre_inmuebles_ventas/` | Alta cobertura para venta en CABA. |
| Mercado Libre | `scrappers/scraper_meli_alquileres_ampliado.py` | Alquiler permanente y temporario | `data/raw/mercadolibre_alquileres/` si se reejecuta; extracciones actuales separadas por operacion en `data/raw/mercadolibre_inmuebles_alquiler*` | Alta cobertura, con segmentacion por barrios para evitar topes de resultados. |
| ArgenProp | `scrappers/scraper_argenprop_inmuebles.py` | Venta y alquiler segun URL de busqueda | `data/raw/argenprop/` | Cobertura baja por bloqueos y ejecucion `--listings-only`. |
| ZonaProp | `scrappers/scraper_zonaprop_inmuebles.py` | Venta y alquiler segun URL de busqueda | `data/raw/zonaprop/` | Cobertura baja/media por bloqueos y ejecucion `--listings-only`. |
| Airbnb | `scrappers/airbnb_caba/` | Alquiler temporario | `data/raw/airbnb/` | Alta cobertura para CABA mediante particion geografica. |
| Airbnb base | `scrappers/scraper_airbnb.py` | Alquiler temporario | `data/raw/airbnb/propiedades_airbnb.csv` | Extraccion inicial limitada; se conserva como antecedente tecnico. |

## Mercado Libre: venta

El script `scrappers/scraper_mercadolibre_ventas.py` releva tarjetas publicas de Mercado Libre Inmuebles para departamentos en venta en CABA.

Caracteristicas principales:

- Recorre paginas de resultados a partir de una URL configurable.
- Extrae atributos visibles de la tarjeta: precio, moneda, titulo, ubicacion declarada, ambientes, banios, dormitorios, superficie, imagen, inmobiliaria y texto de atributos.
- Agrega variables derivadas utiles para el EDA, como comuna aproximada, precio por m2 minimo/maximo, flags de amenities mencionados, monoambiente, apto credito y completitud.
- Guarda un journal JSONL y consolida CSVs con checkpoints, permitiendo reanudar ejecuciones.

Uso sugerido:

```bash
python scrappers/scraper_mercadolibre_ventas.py --help
```

Limitaciones:

- No ingresa a la ficha completa de cada publicacion.
- La ubicacion depende del texto publicado por Mercado Libre y puede no incluir coordenadas exactas.
- Las superficies y ambientes pueden venir como rangos en emprendimientos o publicaciones agregadas.

## Mercado Libre: alquiler permanente y temporario

El script `scrappers/scraper_meli_alquileres_ampliado.py` orquesta extracciones por barrio para alquiler permanente y alquiler temporario. Usa como parser base `scrappers/scraper_mercadolibre_inmuebles_modificado.py`.

Caracteristicas principales:

- Divide la consulta por barrios oficiales de CABA para reducir el limite practico de resultados por busqueda.
- Permite ejecutar alquiler permanente, temporario o ambos.
- Consolida segmentos y deduplica por `item_id`.
- Conserva la fila con mayor `completitud_pct` cuando una publicacion aparece en mas de un segmento.

Uso sugerido:

```bash
python scrappers/scraper_meli_alquileres_ampliado.py --help
```

Limitaciones:

- El barrio surge del segmento de busqueda y/o del texto de la publicacion, por lo que debe validarse durante la limpieza.
- Las publicaciones repetidas entre barrios o modalidades requieren controles de duplicacion adicionales en el EDA.

## ArgenProp

El script `scrappers/scraper_argenprop_inmuebles.py` toma una URL de busqueda de ArgenProp, recorre resultados y puede entrar a cada ficha para extraer informacion detallada. En la corrida actual se uso de forma limitada por bloqueos de IP.

Caracteristicas principales:

- URL de busqueda configurable.
- Respeta robots.txt por defecto.
- Usa reintentos, pausas y checkpoints.
- Extrae campos visibles, JSON-LD y atributos adicionales cuando puede acceder a la ficha.
- Guarda HTMLs de diagnostico ante respuestas bloqueadas o inesperadas.

Uso sugerido:

```bash
python scrappers/scraper_argenprop_inmuebles.py --help
```

Limitaciones:

- La extraccion actual quedo con pocos registros.
- Al usar `--listings-only`, muchas variables de detalle quedan faltantes.
- Se debe tratar como fuente complementaria y no como base principal para comparaciones finas por barrio.

## ZonaProp

El script `scrappers/scraper_zonaprop_inmuebles.py` sigue la misma logica general que el scraper de ArgenProp, adaptada a la estructura de ZonaProp.

Caracteristicas principales:

- URL de busqueda configurable.
- Checkpoints y journal JSONL para reanudar.
- Extraccion de datos de tarjeta y, cuando corresponde, ficha.
- Registro de errores y diagnosticos.

Uso sugerido:

```bash
python scrappers/scraper_zonaprop_inmuebles.py --help
```

Limitaciones:

- La cobertura efectiva es menor que Mercado Libre y Airbnb.
- Puede presentar faltantes en ubicacion precisa, amenities y atributos constructivos.
- Se recomienda usarla como fuente de contraste o complemento.

## Airbnb

El pipeline principal de Airbnb esta documentado en detalle en `docs/scraper_airbnb.md` y en `scrappers/airbnb_caba/README.md`.

Caracteristicas principales:

- Releva CABA mediante particion geografica tipo quadtree para superar el tope de resultados por busqueda.
- Extrae una primera etapa de busqueda y una segunda etapa de ficha completa.
- Genera una version normalizada comparable con portales inmobiliarios.
- Asigna barrio y comuna a partir de coordenadas y GeoJSON oficial de barrios.
- Genera tablas separadas para amenities en formato largo.

Archivos principales:

| Archivo | Uso recomendado |
|---|---|
| `data/raw/airbnb/airbnb_caba_normalizado.csv` | Base principal para comparar alquiler temporario con otras fuentes. |
| `data/raw/airbnb/airbnb_caba_normalizado_mensual.csv` | Serie mensual comparable dentro de su propia ventana de consulta. |
| `data/raw/airbnb/airbnb_caba_listings.csv` | Base amplia, util para auditoria y revision de criterios. |
| `data/raw/airbnb/airbnb_caba_amenities.csv` | Amenities en formato largo. |

Limitaciones:

- El precio depende de fecha, cantidad de noches y cantidad de huespedes.
- Airbnb no informa superficie en m2, direccion exacta ni expensas.
- No debe mezclarse la serie corta con la mensual sin explicitar el regimen de precio.

## Criterios generales para la PreEntrega 2

- Los archivos en `data/raw` son evidencia cruda y no deben modificarse.
- Los datasets limpios y consolidados deben guardarse en `data/processed`.
- Toda decision de limpieza debe quedar documentada en notebooks o en una bitacora de decisiones.
- Las fuentes con baja cobertura no deben sostener conclusiones territoriales fuertes sin aclarar limitaciones.
- Las comparaciones entre venta, alquiler permanente y alquiler temporario deben explicitar diferencias de unidad: precio total, precio mensual, precio por noche, precio por m2 o precio por dormitorio.
