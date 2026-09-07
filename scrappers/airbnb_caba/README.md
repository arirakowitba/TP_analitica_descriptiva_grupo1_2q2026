# Scraper Airbnb — CABA

## Arranque rápido (desde `proyecto_python`, con el venv activado)

    .venv\Scripts\activate
    cd airbnb_caba

    python scrape_search.py --max-cells 2      # PRUEBA DE HUMO, ~1 min
    python export_csv.py                       # ver qué salió

Si la prueba anda, el censo completo (horas) va a un log:

    python -u scrape_search.py --checkin 2026-10-20 --checkout 2026-10-25 >> censo.log 2>&1

Dos detalles de ese comando que no son decorativos:
- El `-u`: sin él Python bufferiza stdout cuando lo mandás a un archivo y el log
  queda en 0 bytes durante horas, así que no podés monitorear nada.
- Las fechas explícitas: el default es `hoy + 45/50 días`, así que si el corrido
  cruza la medianoche y lo reanudás, el default se corre un día y te contamina
  los precios con otra ventana.

Y después la etapa 2 y el export:

    python scrape_pdp.py --limit 5             # prueba de la etapa 2
    python -u scrape_pdp.py >> pdp.log 2>&1    # fichas completas (muchas horas)
    python export_csv.py

Todo es **reanudable**. Si lo cortás con Ctrl+C o se corta la luz, volvés a
correr el mismo comando y sigue donde quedó. Para empezar de cero:
`python scrape_search.py --reset`.

## Las tres etapas

| Etapa | Script | Qué hace | Salida |
|---|---|---|---|
| 1 | `scrape_search.py` | Censo por quadtree sobre el bbox de CABA | `search_raw.jsonl` |
| 2 | `scrape_pdp.py` | Ficha completa de cada anuncio | `pdp_raw.jsonl`, `amenities_raw.jsonl` |
| 3 | `export_csv.py` | Une todo, pivotea amenities, asigna barrio y normaliza | `airbnb_caba_listings.csv`, `airbnb_caba_amenities.csv`, `airbnb_caba_normalizado.csv` |

`barrios.py` + `barrios_caba.geojson` son auxiliares de la etapa 3: ver abajo.

## Por qué el quadtree

Airbnb corta toda consulta en 15 páginas x 18 = ~270 resultados. No hay 16a
página. La única salida es partir el territorio: se busca por bounding box y,
cuando una celda devuelve 15 páginas (está saturada), se la parte en 4 y se
repite. El criterio no es una estimación nuestra: `paginationInfo.pageCursors`
devuelve la cantidad real de páginas cuando está por debajo del tope.

Consecuencia práctica: el árbol baja mucho en Palermo/Recoleta/Centro y casi
nada en el sur. Medido: una celda de ~330 x 440 m en Palermo ya tiene ~100
anuncios.

## Ritmo y bloqueos

`polite_sleep()` mete 1,2 a 2 segundos entre requests. **No lo bajes.** El
censo completo son varias horas y está bien que así sea; el objetivo es no
comerse un bloqueo a mitad de camino, no terminar rápido.

Si el HTML vuelve sin el estado embebido, el script hace backoff exponencial y,
si insiste, devuelve la celda a la cola y corta limpio. Volvés a correrlo más
tarde y retoma.

## El precio: leer esto antes de analizar

El precio de Airbnb **no es un atributo del anuncio**, es una función de fecha,
cantidad de noches y de huéspedes, y no incluye fee de limpieza ni de servicio.

Por eso todo el corrido usa UNA ventana de fechas fija (`--checkin` /
`--checkout`, por defecto 45 a 50 días adelante). Los precios son comparables
entre sí dentro de esa ventana y con nada más. Si repetís el relevamiento otro
mes, o cambiás la ventana, es otra serie: no los mezcles.

`export_csv.py` deja `precio_valor`, `precio_moneda`, `precio_noches` y
`precio_por_noche` (= valor / noches). Y como ~45% de los anuncios vienen con
descuento (`DiscountedDisplayPriceLine`), también `precio_original_valor` y
`descuento_pct`: `precio_valor` es el que se cobra, `precio_original_valor` el
de lista. La moneda sale de `CURRENCY` en
`airbnb_common.py` (por defecto USD; para pesos poné `"ARS"` y verificá que el
string venga con ARS antes de confiar en la conversión).

### Ojo con los promedios: hay precios que no son precios

El 0,9% de los anuncios (107 de 11.276 en el censo del 2026-09-05) informa más
de 1.000 USD por noche, con casos de 89.012 USD. No es un error de parseo:
Airbnb informa eso, verificado en el desglose crudo. Son anfitriones que
bloquean el calendario con un precio impagable en vez de cerrar las fechas.

`export_csv.py` los marca en `precio_sospechoso` y no los borra. Filtralos
antes de promediar: con ellos adentro la media da 211 USD y el desvío 2.234;
sin ellos, 106 y 94. La mediana (79 USD) no se mueve.

## El CSV normalizado, para cruzar con portales inmobiliarios

`airbnb_caba_normalizado.csv` (11.276 filas x 54 columnas) es el mismo dataset
con el vocabulario de un esquema de portal (ZonaProp y similares):
`property_id`, `dormitorios`, `banios`, `toilettes`, `ambientes`, `seller_id`,
`pileta`, `parrilla`, `ascensor`, etc. Sirve para que los dos datasets se
puedan cruzar hablando el mismo idioma.

Sólo tiene los campos que Airbnb realmente informa. Los que no existen
—superficie, expensas, dirección, antigüedad, apto_credito— no están, en vez de
aparecer como columnas vacías que confundan.

De dónde salen los campos de estructura: Airbnb no los da como campos, los mete
en el resumen ("... · 1 dormitorio · 2 camas · 1 baño"). El export los parsea,
con esta cobertura medida: dormitorios 99,7%, baños 99,4%, camas 97,9%. Dos
convenciones traducidas:
- "Estudio" es monoambiente => `dormitorios` = 0, `ambientes` = 1.
- "1,5 baños" son 1 baño completo + 1 toilette: de ese número salen `banios`
  y `toilettes`.

`ambientes` es dormitorios + 1 por la convención local. Es un cálculo nuestro,
NO un dato de Airbnb.

Tres columnas son constantes, y están porque el esquema las pide: `amoblado`
(todo Airbnb lo está), `tipo_operacion` (alquiler_temporario) y `unidad_precio`
(por_noche_2_huespedes_5_noches). Esta última es la advertencia importante: el
`precio` de este dataset NO es comparable con un precio de venta ni con un
alquiler mensual.

## El censo cuenta oferta disponible, no anuncios totales

El censo del 2026-09-05 dio 11.276 anuncios, contra los ~25-30k que reporta
Inside Airbnb para CABA. No falta cobertura: la búsqueda sólo devuelve lo
**disponible para la ventana de fechas y para 2 huéspedes**. Quedan afuera los
bloqueados, los de mínimo de noches incompatible y los de capacidad 1. Si lo
que necesitás es el universo de anuncios, eso es Inside Airbnb.

## El barrio sale de las coordenadas, no de Airbnb

Airbnb dejó de devolver el barrio (verificado en la corrida del 2026-09-05). En
modo mapa —el único que acepta bounding box— el `title` del resultado viene
null; en modo lista pasó a decir "Departamento en Buenos Aires", la ciudad. La
PDP tampoco lo trae. El detalle está en `HALLAZGOS.md`.

Así que `export_csv.py` lo deduce de las coordenadas con `barrios.py`: ray
casting en Python puro contra `barrios_caba.geojson`, el GeoJSON oficial de los
48 barrios. Sin dependencias nuevas. Deja dos columnas: `barrio` y `comuna`.

    python barrios.py      # autotest con 10 puntos conocidos

Dos cosas para tener presente al analizar:
- La precisión de la coordenada NO es uniforme. `radio_ofuscacion_m` (lo que
  Airbnb declara como radio del círculo del mapa) dio: **0 m en el 52%** de los
  anuncios, con la coordenada redondeada a 4 decimales (~11 m); **152 m en el
  44%**; **500 m en el 4%**. Para agregar por barrio alcanza en los tres casos;
  para algo más fino, filtrar `radio_ofuscacion_m == 0`.
- `barrio` nulo significa "fuera del polígono de CABA": el bounding box tiene
  margen y entran anuncios de GBA. Es la forma de filtrarlos.

Si falta `barrios_caba.geojson`, bajalo de:

    https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/barrios/barrios.geojson

## Qué NO trae esto

Sin metros cuadrados, sin dirección exacta (las coordenadas están desplazadas
hasta ~150 m a propósito), sin expensas, sin antigüedad. No existen del lado de
Airbnb. Si el análisis los necesita, el cruce es contra ZonaProp a nivel barrio,
no a nivel unidad.

Tampoco trae el calendario diario a 365 días ni el histórico de reviews: eso lo
da Inside Airbnb (corte 2026-07-24, descarga manual desde el navegador en
https://insideairbnb.com/get-the-data/ porque el proxy de la empresa bloquea
ese dominio).

## La base cruda: mejorar el parser sin re-scrapear

Los scrapers guardan además la **respuesta cruda comprimida**:
`pdp_full*.jsonl.gz` (~28 KB por anuncio) y `search_full*.jsonl.gz`. Sirve para
una cosa concreta: cuando descubrís un campo que el parser no estaba leyendo,
lo recuperás sin volver a pedirle nada a Airbnb.

    python reparse.py                    # re-parsea la serie base desde el crudo
    python reparse.py --sufijo _mensual  # la serie mensual
    python reparse.py --que pdp          # sólo las fichas

Deja `.bak` antes de sobrescribir, así que si el parser nuevo sale peor volvés
atrás. Está verificado que el re-parseo reproduce el archivo original byte por
byte.

Si te importa el espacio, `--sin-crudo` desactiva el guardado. No te lo
recomiendo: en la primera corrida hubo que re-scrapear tres veces por campos
descubiertos tarde, y cada una costó horas.

## Series con distinta ventana de fechas

Cada ventana es una serie aparte y NO se mezclan. `--sufijo` cambia todos los
archivos de salida:

    python -u scrape_search.py --sufijo _mensual --checkin 2026-10-20 --checkout 2026-11-19
    python -u scrape_pdp.py --sufijo _mensual --reusar-fichas pdp_raw.jsonl
    python export_csv.py --sufijo _mensual

`--reusar-fichas` es la clave de que la segunda serie sea barata: la ficha es
del anuncio, no de la ventana de fechas, así que sólo se bajan las que faltan.
En la serie mensual fueron 1.508 de 10.369: una hora en vez de siete.

El export lee las dos fuentes de fichas (la propia y la base) y las concatena.

## Nota de mantenimiento

Los dos identificadores frágiles están en un solo lugar cada uno:
`PDP_HASH` en `scrape_pdp.py` y `API_KEY` en `airbnb_common.py`. Si un día la
etapa 2 empieza a devolver `ValidationError`, es que Airbnb cambió el hash de
la persisted query: se recupera abriendo cualquier anuncio con la pestaña de
red del navegador abierta y copiando el hash de la llamada a
`/api/v3/StaysPdpSections/<hash>`.
