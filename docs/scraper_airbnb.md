# Scraper Airbnb CABA — documentación técnica

**Corte de datos: 5 y 6 de septiembre de 2026.**
Salida: 6 CSV en `data_raw/airbnb/`, 11.276 + 10.369 anuncios.

---

## 1. Problema que resuelve

Se necesitaba relevar la oferta de alquiler temporario de Airbnb en la Ciudad de
Buenos Aires —precio, ubicación, atributos del inmueble, anfitrión y
reputación— para poder cruzarla contra la oferta de los portales inmobiliarios
(ZonaProp, ArgenProp, MercadoLibre) que releva el resto del proyecto.

Airbnb no tiene API pública ni exportación de datos, y el sitio impone cuatro
obstáculos concretos:

**1. El contenido se renderiza en el cliente.** Un `requests.get()` ingenuo al
HTML no encuentra los datos en el DOM. Se evaluó y descartó usar Selenium o
Playwright: Airbnb embebe el estado inicial completo de React en el HTML, dentro
de `<script id="data-deferred-state-0">`, así que alcanza con un GET y
`json.loads`. Sin navegador, sin drivers, sin clases CSS que se rompen.

**2. Toda consulta se corta en ~270 resultados.** Máximo 15 páginas × 18
resultados, confirmado empíricamente: no existe una página 16. Un scraper que
pagina hasta el final obtiene unos cientos de anuncios y cree haber terminado.
El scraper que ya estaba en `data_raw/airbnb/propiedades_airbnb.csv` ilustra el
problema: su `checkpoint_state.json` registra `last_page: 55` y
`unique_properties: 29`, o sea 55 páginas recorridas para 29 anuncios únicos.
La solución acá es un **quadtree geográfico** (ver sección 3).

**3. El barrio ya no viene en los datos.** Airbnb dejó de exponerlo: en modo
mapa el campo `title` del resultado viene `null`, y en modo lista pasó a decir
"Departamento en Buenos Aires" —la ciudad, no el barrio—. La página de detalle
tampoco lo trae. Se resuelve deduciéndolo de las coordenadas contra el GeoJSON
oficial de los 48 barrios.

**4. El precio no es un atributo del inmueble.** Es el resultado de una función
de (fecha de entrada, fecha de salida, cantidad de huéspedes). El mismo
departamento, relevado el mismo día, devuelve cuatro números distintos según lo
que se le pregunte. Por eso todo el relevamiento usa **una ventana de fechas
fija por serie** y la unidad viaja pegada al dato en la columna `unidad_precio`.
Ver sección 4.

---

## 2. Archivos y carpetas del proyecto

El pipeline son 6 módulos Python, 1.623 líneas en total. Ninguno depende de nada
más que `requests` y `pandas`.

### `airbnb_common.py` — 161 líneas

Infraestructura compartida. No tiene lógica de negocio.

- **Constantes**: `API_KEY` (clave pública de Airbnb, constante desde hace años,
  está en el propio HTML), `HOST` (`https://www.airbnb.com.ar`), `LOCALE`
  (`es-AR`), `CURRENCY` (`USD`), `DEFERRED_RE` (el regex que extrae el JSON
  embebido), `HEADERS` (User-Agent de Chrome + `Accept-Language: es-AR`).
- **`new_session()`**: una `requests.Session` con los headers puestos. Reusar la
  sesión mantiene el keep-alive y las cookies.
- **`polite_sleep(base=1.2, jitter=0.8)`**: duerme entre 1,2 y 2 segundos.
  **No bajar.** El cuello de botella es deliberado: en ~23.000 requests no hubo
  un solo bloqueo.
- **`get_deferred_state(session, url, retries=4)`**: GET + extracción del JSON
  embebido, con backoff exponencial. Distingue tres fallas: excepción de red
  (espera 4·2^n), HTTP 429/5xx (espera 10·2^n) y HTML sin el estado embebido
  (espera 8·2^n, y si insiste levanta `Blocked` — eso es un bloqueo, no un bug).
- **`make_cursor(items_offset)`**: el cursor de paginación **no hay que
  scrapearlo**, es base64 de `{"section_offset":0,"items_offset":N,"version":1}`
  con N saltando de 18 en 18.
- **`b64` / `unb64` / `listing_id_from_gid`**: los IDs de Airbnb viajan en
  base64 (`"DemandStayListing:1234"`).
- **`jsonl_append` / `jsonl_ids`**: escritura incremental y lectura de IDs ya
  guardados, que es lo que hace todo reanudable.
- **`jsonl_gz_append` / `jsonl_gz_read`**: guardado de la respuesta **cruda**
  comprimida, en gzip multi-miembro (cada append abre un miembro nuevo y
  `gzip.open()` los concatena al leer). Ver `reparse.py`.

### `scrape_search.py` — 321 líneas — ETAPA 1

El censo de anuncios por quadtree geográfico. Ver sección 3.

- **Constantes**: `CABA` (el bounding box: `ne_lat=-34.5265, ne_lng=-58.3350,
  sw_lat=-34.7050, sw_lng=-58.5310`), `PAGE_SIZE=18`, `MAX_PAGES=15` (el tope
  duro de Airbnb), `MIN_CELL_DEG=0.0015` (~150 m, piso para no recursar
  infinito), `PRECIO_CONOCIDOS` (guarda contra cambios de formato).
- **`build_url(cell, page, checkin, checkout, adults)`**: arma la URL de
  búsqueda por bounding box.
- **`fetch_page()`**: baja una página y devuelve los nodos y la cantidad real de
  páginas (`paginationInfo.pageCursors`).
- **`parse_result(node, cell, checkin, checkout)`**: de cada resultado saca 27
  campos. Acá está el manejo de los dos typenames de precio (ver sección 3).
- **`split(cell)` / `too_small(cell)`**: la subdivisión en 4 y el corte por
  tamaño mínimo.
- **`_avisar()` / `AVISOS`**: acumula estructuras que el parser no supo leer y
  las grita al final de la corrida.
- **Salidas**: `search_raw.jsonl` (un registro parseado por anuncio),
  `search_full.jsonl.gz` (nodos crudos), `cells_pending.json` (la cola del
  quadtree = el checkpoint).

### `scrape_pdp.py` — 366 líneas — ETAPA 2

La ficha completa de cada anuncio. Ver sección 3.

- **Constantes**: `PDP_HASH` (el hash de la persisted query de GraphQL; es el
  identificador frágil del proyecto), `GP` y `MIG` (las listas de fragmentos a
  activar: 35 y 40 flags).
- **`build_variables(listing_id, checkin, checkout, adults)`**: arma las
  ~50 variables del payload, incluidos los flags `includeGp<X>Fragment` e
  `includePdpMigration<X>Fragment` en `true`. Poniéndolos todos, toda la ficha
  vuelve en **una sola** llamada.
- **`fetch_pdp()`**: el POST, con reintentos y backoff en 429/5xx.
- **`parse(listing_id, j)`**: de las ~23 secciones con cuerpo extrae 55 campos
  planos más la tabla larga de amenities.
- **Salidas**: `pdp_raw.jsonl`, `amenities_raw.jsonl` (un registro por anuncio ×
  amenity), `pdp_full.jsonl.gz` (respuesta cruda, ~28 KB comprimidos por
  anuncio).

### `barrios.py` — 134 líneas

Asignación de barrio por coordenadas, en Python puro. Sin `shapely` ni
`geopandas`.

- **`load(path)`**: parsea `barrios_caba.geojson` a
  `[(nombre, comuna, bbox, [polígonos])]`, con caché en memoria.
- **`_en_anillo(x, y, anillo)`**: ray casting. Cuenta cruces de la horizontal
  que pasa por el punto.
- **`_en_poligono()`**: maneja anillos exteriores y agujeros.
- **`barrio_de(lat, lon)`**: devuelve `(nombre, comuna)` o `(None, None)` si
  cae fuera de CABA. Descarta por bounding box antes de hacer el ray casting:
  25.000 puntos en 1,4 segundos.
- **Autotest**: `python barrios.py` corre 10 puntos conocidos (Obelisco →
  San Nicolas, Caminito → La Boca, etc.). Da 10/10.

### `export_csv.py` — 528 líneas — ETAPA 3

Consolidación y derivación. Es el único módulo que usa `pandas`.

- **`parse_precio(txt)`**: `'$ 220 USD'` a `(220.0, 'USD')`. Formato es-AR
  (punto de miles, coma decimal) y tolera los espacios no separables (U+00A0)
  que usa Airbnb.
- **`parse_noches(qualifier)` / `parse_regimen()`**: `"por 5 noches"` a 5;
  `"mensual"` a 30 y régimen `mensual`.
- **`parse_estructura(resumen, detalle)`**: extrae dormitorios, camas y baños
  del texto del resumen. Traduce dos convenciones de Airbnb: `"Estudio"` es
  monoambiente (0 dormitorios, no un dato faltante) y `"1,5 baños"` son 1 baño
  completo + 1 toilette.
- **`categoria_alojamiento()`**: separa `vivienda_entera` /
  `habitacion_en_vivienda` / `hotelero` / `no_vivienda`.
- **`slug()` / `sin_acentos()` / `FAMILIAS`**: el pivote de amenities y su
  agrupación por concepto.
- **`validar(df, hay_fichas)`**: compara la cobertura de 16 columnas clave
  contra un piso esperado y grita si algo cayó. Ver sección 3.
- **`escribir_csv()`**: tolera `PermissionError` (el CSV abierto en Excel) en
  vez de morirse a mitad de la escritura.
- **`escribir_normalizado(df, suf)`**: el CSV con vocabulario de portal.
- **Salidas**: `airbnb_caba_listings.csv`, `airbnb_caba_normalizado.csv`,
  `airbnb_caba_amenities.csv` (y sus pares `_mensual`).

### `reparse.py` — 113 líneas

Re-parsea desde las respuestas crudas guardadas, **sin tocar la red**.

Existe porque los `.jsonl` guardan el registro ya parseado: cada campo
descubierto tarde exigía volver a scrapear (pasó tres veces). Con el crudo en
disco, mejorar el parser son minutos de CPU. Deja `.bak` antes de sobrescribir.
Verificado: el re-parseo reproduce el archivo original **byte por byte**.

### Archivos de datos y de estado

| archivo | qué es |
|---|---|
| `barrios_caba.geojson` | 723 KB. GeoJSON oficial de los 48 barrios (CRS84). **Es una dependencia del código**, no un dato relevado: sin él `barrios.py` no corre. |
| `search_raw*.jsonl` | Un registro parseado por anuncio del censo. |
| `pdp_raw*.jsonl` | Una ficha por anuncio. |
| `amenities_raw*.jsonl` | Tabla larga: un registro por (anuncio, amenity). |
| `*_full*.jsonl.gz` | Respuestas crudas comprimidas. Insumo de `reparse.py`. |
| `cells_pending*.json` | La cola del quadtree. **Es el checkpoint**: borrarlo pierde el estado. |
| `requirements.txt` | Versiones exactas. |

---

## 3. Cómo se hizo cada extracción

### Fuente y descubrimiento

Todo sale de dos endpoints de `www.airbnb.com.ar`:

| etapa | método | endpoint | formato |
|---|---|---|---|
| 1 — censo | GET | `/s/homes?<bbox>&<fechas>&cursor=` | HTML con JSON embebido |
| 2 — ficha | POST | `/api/v3/StaysPdpSections/<hash>` | GraphQL persisted query |

El JSON embebido está en `<script id="data-deferred-state-0">`, y la ruta interna
es `j["niobeClientData"][0][1]["data"]["presentation"]["staysSearch"]`.

La API key (`d306zoyjsyarp7ifhu67rjxn52tv0t20`) es pública y viene en el propio
HTML como `"api_config":{"key":"…"}`.

### Etapa 1 — censo por quadtree

El problema es el techo de ~270 resultados. La solución es **particionar el
territorio** en vez de paginar:

1. Se arranca con una celda: el bounding box completo de CABA.
2. Se pide la página 0 y se lee `paginationInfo.pageCursors`, que devuelve la
   **cantidad real de páginas** cuando está por debajo del tope.
3. Si son 15 páginas, la celda está saturada (hay más anuncios de los que
   Airbnb va a mostrar): se la parte en 4 y cada hija vuelve a la cola.
4. Si son menos de 15, la celda entra completa: se recorren sus páginas
   restantes y se termina.
5. Se repite hasta que la cola queda vacía.

El criterio de corte no es una estimación propia: es un dato que devuelve
Airbnb. El árbol baja mucho en Palermo/Recoleta/Centro y casi nada en el sur.
La corrida real fueron **147 celdas** para 11.276 anuncios.

De cada resultado se leen 27 campos. Además de `searchResults` (18 por página)
se toma `mapResults.mapSearchResults` (20 por página), que a veces trae anuncios
que no entran en la lista.

**El detalle que más importó del parseo.** `structuredDisplayPrice.primaryLine`
viene con dos `__typename` distintos y **claves distintas**:

| `__typename` | claves | serie corta | serie mensual |
|---|---|---|---|
| `QualifiedDisplayPriceLine` | `price` | 68% | 8% |
| `DiscountedDisplayPriceLine` | `discountedPrice` + `originalPrice` | 32% | **92%** |

Leer sólo `price` deja el precio en `null` sin tirar ningún error. En la serie
mensual, donde casi todo anuncio aplica descuento por estadía larga, eso habría
destruido el 92% del dataset. Por eso el parser cae a `discountedPrice`, guarda
`originalPrice` aparte, y existe la lista `PRECIO_CONOCIDOS`: si Airbnb agrega
un typename nuevo, la corrida termina avisándolo con las claves exactas que
trajo la estructura desconocida.

### Etapa 2 — ficha completa (PDP)

Las secciones de la página de detalle no vienen en el HTML inicial: se piden con
un POST a `/api/v3/StaysPdpSections/<hash>`. Reconstruir las `variables` a mano
devuelve `ValidationError`; la forma exacta se lee de la clave
`j["niobeClientData"][0][0]` del propio JSON embebido, que es un string
`"StaysPdpSections:{…variables…}"`.

Poniendo en `true` los ~75 flags `includeGp<X>Fragment` e
`includePdpMigration<X>Fragment`, **toda la ficha vuelve en una sola llamada**:
23 secciones con cuerpo. De ahí salen:

- `sections.metadata.loggingContext.eventDataLogging`: plano y listo para CSV —
  `roomType`, `personCapacity`, `isSuperhost`, `guestSatisfactionOverall` y las
  6 dimensiones de rating.
- `AMENITIES_DEFAULT`: 36 a 47 amenities por anuncio, con `available` true/false
  (o sea también lo que el anuncio **no** tiene).
- `POLICIES_DEFAULT`, `MEET_YOUR_HOST`, `DESCRIPTION_DEFAULT`, `LOCATION_PDP`,
  `PHOTO_TOUR_SCROLLABLE`, `HIGHLIGHTS_DEFAULT`.

La ficha **no depende de la ventana de fechas**, así que la serie mensual reusó
las 8.861 fichas ya bajadas y sólo pidió 1.508 nuevas: 1 hora en vez de 7.

### Etapa 3 — consolidación

`pandas` para unir censo + fichas, pivotear amenities y derivar columnas.

Dos decisiones del pivote de amenities: hay **3.362 nombres distintos** porque
Airbnb deja que el anfitrión escriba el detalle ("Horno de inducción de acero
inoxidable de Samsung"), y 1.538 aparecen en un solo anuncio. Se pivotean sólo
los que están en al menos el 1% de los anuncios (169 columnas) y se agregan 32
columnas `fam_*` que agrupan por concepto (`fam_calefaccion` junta
"Calefacción", "Calefacción: sistema sin conductos tipo split" y "Calefacción
radiante"). La tabla larga completa queda en `airbnb_caba_amenities.csv`, sin
recortes.

### Librerías

| librería | para qué |
|---|---|
| `requests` 2.33.1 | todo el HTTP: sesión, GET del HTML, POST de GraphQL |
| `pandas` 3.0.2 | sólo en la etapa 3: unión, pivote, CSV |
| estándar | `re` (JSON embebido y parseo de textos), `json`, `base64` (cursor e IDs), `gzip` (crudo), `argparse`, `pathlib`, `time`/`random` (rate limit) |

**No se usa** Selenium, Playwright, BeautifulSoup, lxml, shapely ni geopandas.
El ray casting de `barrios.py` y el parseo del JSON embebido están en Python
puro justamente para no sumar dependencias.

### Guardas contra la falla silenciosa

La falla peligrosa de este pipeline no es que rompa: es que produzca un dataset
incompleto que parece completo. El bug del precio no tiró ningún error, dejó el
32% de las filas en `null`. Hay dos guardas:

1. **`PRECIO_CONOCIDOS` + `AVISOS`** en `scrape_search.py` (descrito arriba).
2. **`validar()`** en `export_csv.py`: compara 16 columnas clave contra un piso
   de cobertura y lista las que caen. Los pisos respetan los nulos legítimos
   (`barrio` 90% por los anuncios de GBA que entran por el margen del bbox,
   `rating_general` 70% por los anuncios sin reseñas). Probado reproduciendo el
   bug viejo sobre el dataset real: detecta las tres columnas caídas.

---

## 4. El dataset final

### Los seis archivos

| archivo | filas | columnas | MD5 |
|---|---|---|---|
| `airbnb_caba_normalizado.csv` | 10.326 | 58 | `c897dcdbed8c98d0624740d911029974` |
| `airbnb_caba_listings.csv` | 11.276 | 286 | `e4ceebbb7f1957d757c201c641544088` |
| `airbnb_caba_amenities.csv` | 416.395 | 6 | `53a33fb9c95fb313997e14a52fa0357d` |
| `airbnb_caba_normalizado_mensual.csv` | 9.596 | 59 | `48b3cb5eb8f5007f4ab07999506b3007` |
| `airbnb_caba_listings_mensual.csv` | 10.369 | 287 | `ba3009012f35587988f2934f2d6a8ba3` |
| `airbnb_caba_amenities_mensual.csv` | 466.706 | 6 | `b51a2d1b2ccf8b4c3d17c2f3fb10f940` |

Verificar: `certutil -hashfile <archivo> MD5`

### Las dos series NO se mezclan

| | serie corta | serie mensual |
|---|---|---|
| ventana cotizada | 2026-10-20 a 10-25 (5 noches) | 2026-10-20 a 11-19 (30 noches) |
| huéspedes | 2 | 2 |
| anuncios | 11.276 | 10.369 |
| precio mediano | USD 79 / noche | USD 1.783 / mes (60,6 / noche) |

Mismo día de inicio para que compartan estacionalidad. **El precio de una serie
no es comparable con el de la otra sin tener en cuenta el descuento por estadía
larga** (22,3% mediano; el 95% de los anuncios lo aplica).

### `airbnb_caba_normalizado.csv` — 58 columnas

Es el archivo por el que conviene empezar: vivienda entera únicamente, con el
vocabulario del esquema de portales del proyecto.

| columna | tipo | cobertura | ejemplo |
|---|---|---|---|
| `property_id` | int64 | 100% | `941997550078704265` |
| `fuente` | str | 100% | `airbnb` |
| `tipo_operacion` | str | 100% | `alquiler_temporario` |
| `unidad_precio` | str | 100% | `por_noche_2_huespedes_5_noches` |
| `url` | str | 100% | `https://www.airbnb.com.ar/rooms/941997550078704265` |
| `scraped_at_utc` | str | 100% | `2026-09-06T00:55:31Z` |
| `titulo` | str | 100% | `Cálido Mono ambiente con pileta` |
| `descripcion` | str | 99,8% | `Espacio amplio y confortable ubicado a 500 metros...` |
| `tipo_propiedad` | str | 100% | `Vivienda alquilada entero` |
| `room_type` | str | 100% | `Entire home/apt` |
| `categoria_alojamiento` | str | 100% | `vivienda_entera` |
| `es_vivienda` | bool | 100% | `True` |
| `acepta_larga_estadia` | bool | 100% | `True` |
| `precio_regimen` | str | 100% | `por_noche` |
| `moneda` | str | 100% | `USD` |
| `precio` | float64 | 100% | `42.0` |
| `precio_texto` | str | 100% | `$ 210 USD` |
| `precio_sospechoso` | bool | 100% | `False` |
| `barrio` | str | 99,2% | `Colegiales` |
| `comuna` | float64 | 99,2% | `13.0` |
| `latitud` | float64 | 100% | `-34.5752` |
| `longitud` | float64 | 100% | `-58.4481` |
| `ambientes` | float64 | 100% | `2.0` |
| `dormitorios` | float64 | 100% | `1.0` |
| `banios` | float64 | 99,9% | `1.0` |
| `toilettes` | float64 | 99,9% | `0.0` |
| `camas` | float64 | 98,1% | `1.0` |
| `capacidad` | int64 | 100% | `3` |
| `seller_id` | int64 | 100% | `311393874` |
| `seller_nombre` | str | 100% | `Silvia` |
| `seller_superhost` | bool | 100% | `True` |
| `rating` | float64 | 87,7% | `4.86` |
| `reviews` | float64 | 87,7% | `97.0` |
| `cantidad_imagenes` | int64 | 100% | `18` |
| `imagen_principal` | str | 100% | `https://a0.muscache.com/im/pictures/...` |
| `ascensor`, `balcon_o_patio`, `terraza`, `jardin`, `parrilla`, `pileta`, `gimnasio`, `sauna`, `laundry`, `cochera`, `camaras_seguridad`, `portero`, `aire_acondicionado`, `calefaccion`, `losa_radiante`, `internet`, `vista`, `zona_trabajo`, `permite_mascotas` | bool | 100% | `True` / `False` |
| `amoblado` | bool | 100% | `True` (constante: todo Airbnb lo está) |
| `localidad` | str | 100% | `Ciudad Autónoma de Buenos Aires` |
| `provincia` | str | 100% | `CABA` |
| `pais` | str | 100% | `Argentina` |

Los nulos son legítimos: `barrio` nulo significa fuera del polígono de CABA (95
anuncios que entran por el margen del bbox); `rating` nulo significa anuncio sin
reseñas.

### Ejemplo de una fila completa

```
property_id            941997550078704265
fuente                 airbnb
tipo_operacion         alquiler_temporario
unidad_precio          por_noche_2_huespedes_5_noches
url                    https://www.airbnb.com.ar/rooms/941997550078704265
scraped_at_utc         2026-09-06T00:55:31Z
titulo                 Cálido Mono ambiente con pileta
tipo_propiedad         Vivienda alquilada entero
room_type              Entire home/apt
categoria_alojamiento  vivienda_entera
precio_regimen         por_noche
moneda                 USD
precio                 42.0
precio_texto           $ 210 USD
precio_sospechoso      False
barrio                 Colegiales
comuna                 13.0
latitud                -34.5752
longitud               -58.4481
ambientes              2.0
dormitorios            1.0
banios                 1.0
toilettes              0.0
camas                  1.0
capacidad              3
seller_id              311393874
seller_nombre          Silvia
seller_superhost       True
rating                 4.86
reviews                97.0
cantidad_imagenes      18
pileta                 True
terraza                True
aire_acondicionado     True
calefaccion            True
internet               True
amoblado               True
localidad              Ciudad Autónoma de Buenos Aires
```

### `airbnb_caba_listings.csv` — 286 columnas

Todo, sin recortar. Se descompone en:

- **86 columnas de datos**: identidad (`listing_id`, `url`, `celda`), precio
  (12 columnas, incluidos los textos crudos), ubicación, estructura, reputación
  (rating general + 6 dimensiones), anfitrión (11 columnas), textos y reglas.
- **168 columnas `am_*`**: un amenity por columna, `True` / `False` / vacío.
- **32 columnas `fam_*`**: familias agrupadas por concepto.

**Cuidado al leer los amenities**: el `False` es dato real, Airbnb lista
explícitamente lo que el anuncio **no** tiene. "Detector de humo" aparece
mencionado en el 100% de los anuncios pero sólo el 25% lo tiene. Para analizar
conviene usar las `fam_*`, que cuentan disponibilidad real.

### `airbnb_caba_amenities.csv` — 6 columnas, formato largo

`listing_id`, `grupo`, `amenity`, `subtitulo`, `disponible`, `icono`. Un
registro por (anuncio, amenity), ~37 por anuncio. Tiene los 3.362 amenities
completos y la taxonomía de 16 grupos de Airbnb, que el pivote pierde.

### Advertencias de uso

**Filtrar `precio_sospechoso` antes de promediar.** 107 anuncios informan más de
USD 1.000 por noche, con un máximo de 89.012. No es un error de parseo:
verificado contra el desglose crudo, Airbnb informa eso. Son anfitriones que
bloquean el calendario con un precio impagable en vez de cerrar las fechas. Con
ellos adentro la media da 211 USD y el desvío 2.234; sin ellos, 106 y 94. La
mediana (79) no se mueve.

**El censo es oferta disponible, no el padrón de anuncios.** Inside Airbnb
reporta 25-30k anuncios en CABA; acá hay 11.276 porque la búsqueda sólo devuelve
lo que acepta esa estadía: queda afuera lo ocupado, lo que exige otro mínimo de
noches y lo que no entra con 2 huéspedes.

**La precisión de las coordenadas es de tres niveles, no uno.** Airbnb declara
en `radio_ofuscacion_m` el radio del círculo que dibuja en el mapa, y la
distribución real del dataset es:

| radio declarado | anuncios | decimales de la coordenada | qué significa |
|---|---|---|---|
| 0 m | 5.840 (52%) | 4 | coordenada redondeada a una grilla de ~11 m, con marcador exacto |
| 152 m | 4.974 (44%) | 5 o más | coordenada desplazada: el punto real está dentro de ese radio |
| 500 m | 433 (4%) | 5 o más | idem, dentro de 500 m |

Son dos mecanismos distintos: los de radio 0 tienen la coordenada truncada a 4
decimales, y los de radio 152 y 500 tienen precisión completa pero desplazada.
Hay además 52 anuncios con sólo 2 decimales (~1,1 km).

Para agregar por barrio la precisión alcanza en los tres grupos. Para algo más
fino (manzana, distancia a un subte, frente sobre una avenida) sólo sirven los
5.840 de `radio_ofuscacion_m == 0`. Y en ningún caso permite identificar la
unidad: sin calle, altura ni piso, no hay forma de saber qué inmueble es.
Una salvedad sobre la interpretación: lo **medido** es la distribución de
`radio_ofuscacion_m` y la cantidad de decimales de cada coordenada. Que los de
radio 0 tengan la coordenada real (sólo redondeada) y los de radio 152 la tengan
desplazada es la lectura más razonable de ese patrón, pero **no se pudo
verificar**: haría falta la dirección real de algún anuncio para comparar, y
Airbnb no la da. Tratar el radio como una cota superior del error, no como una
medición del error.


**Una fila es una publicación, no una propiedad.** Los `normalizado` ya vienen
filtrados a `vivienda_entera`; en los `listings` hay además 516 habitaciones
privadas (varias pueden ser del mismo departamento) y 391 alojamientos
hoteleros, separados en `categoria_alojamiento`.

**Datos personales.** Los `listings` incluyen `host_nombre`, `host_sobre_mi`
(biografías escritas por los anfitriones), `descripcion` y `host_id`: datos
personales de unos 5.600 anfitriones identificables.

### Lo que el dataset NO tiene

Metros cuadrados, dirección exacta, expensas y antigüedad: **no existen del lado
de Airbnb**. Por eso no hay precio por m² y el cruce con los portales es **a
nivel barrio, no a nivel unidad**.

Tampoco tiene los fees de limpieza y servicio (el costo real al huésped es
15-25% mayor), el mínimo de noches exacto, el calendario a 365 días ni el texto
de las reseñas. El mínimo de noches se aproxima con `acepta_larga_estadia` /
`solo_larga_estadia`, que salen de cruzar las dos series.

---

## 5. Reproducir desde cero

### Requisitos

- **Python 3.14** (probado en 3.14.3). Debería andar en 3.10+.
- **Acceso de red a `airbnb.com.ar` y `muscache.com`.** Muchos proxies
  corporativos los bloquean: hay que correrlo desde una red que no lo haga.
- ~400 MB de disco (187 MB de CSV, 140 MB de `.jsonl`, y ~315 MB más si se
  activa el guardado de crudo).

### Variables de entorno

**El pipeline no usa ninguna.** No hay claves, tokens ni archivos `.env`: la API
key de Airbnb es pública y está hardcodeada en `airbnb_common.py`.

La única que conviene setear en Windows es la del encoding de la consola, porque
los textos tienen acentos y la consola por defecto usa cp1252:

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

Sin eso, los `print` con acentos pueden cortar el script con
`UnicodeEncodeError`. No afecta a los archivos de salida, que siempre se
escriben en UTF-8.

### Instalación

```powershell
cd C:\ruta\del\proyecto
python -m venv .venv
.venv\Scripts\activate
pip install requests==2.33.1 pandas==3.0.2
```

**Atención con el `requirements.txt` de la raíz del repo**: lista
`beautifulsoup4`, `lxml`, `playwright`, `requests` y `urllib3` —las
dependencias de los otros scrapers del proyecto— y **no incluye `pandas`**, que
este pipeline necesita para la etapa 3. Tampoco fija versiones.

Este scraper corre con exactamente dos dependencias directas:

```
requests==2.33.1
pandas==3.0.2
```

El pipeline trae su propio `requirements.txt` con esas dos y sus transitivas
(`numpy`, `certifi`, `charset-normalizer`, `idna`, `urllib3`,
`python-dateutil`, `six`, `tzdata`). Cuando el código se suba al repo, usar ése:

```powershell
pip install -r requirements.txt
```

No hace falta `playwright`, `beautifulsoup4` ni `lxml`: este scraper no usa
navegador ni parsea HTML.

El GeoJSON de barrios va incluido en el repo. Si falta:

```powershell
curl -o barrios_caba.geojson https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/barrios/barrios.geojson
```

Verificar que quedó bien:

```powershell
python barrios.py
```

Tiene que dar 10/10 correctos.

### Comandos, en orden

**Paso 1 — prueba de humo (~2 min).** No saltear: valida red y parseos antes de
comprometer horas.

```powershell
$env:PYTHONIOENCODING = "utf-8"
python scrape_search.py --max-cells 2 --checkin 2026-10-20 --checkout 2026-10-25
python export_csv.py
```

Criterio de éxito: `search_raw.jsonl` con decenas de anuncios y `precio_valor`,
`latitud`, `longitud`, `cantidad_fotos` poblados. La validación tiene que decir
`validación: OK`.

**Paso 2 — prueba de la etapa 2 (~1 min).**

```powershell
python scrape_pdp.py --limit 5 --checkin 2026-10-20 --checkout 2026-10-25
python export_csv.py
```

Criterio: `pdp_raw.jsonl` con 5 líneas, `amenities_raw.jsonl` con ~40 amenities
por anuncio, y `rating_general` / `capacidad` / `es_superhost` / `host_id`
poblados. Si da `ValidationError`, cambió el `PDP_HASH` (ver diagnóstico).

**Paso 3 — censo completo (~35 min).** Arrancar de cero con `--reset`.

```powershell
python -u scrape_search.py --reset --checkin 2026-10-20 --checkout 2026-10-25 >> censo.log 2>&1
```

Dos detalles de ese comando que **no son opcionales**:

- **`-u`**: sin él Python bufferiza stdout cuando el destino es un archivo y el
  log queda en 0 bytes durante horas. No se puede monitorear nada.
- **Las fechas explícitas**: el default es `hoy + 45/50 días`. Si el corrido
  cruza la medianoche y se reanuda, el default se corre un día y **contamina los
  precios con otra ventana**, en silencio.

**Paso 4 — fichas completas (~8 h).**

```powershell
python -u scrape_pdp.py --checkin 2026-10-20 --checkout 2026-10-25 >> pdp.log 2>&1
```

~2,5 segundos por anuncio. Es reanudable: si se corta, el mismo comando retoma.

**Paso 5 — consolidación (~2 min).**

```powershell
python export_csv.py
```

**Paso 6 — la serie mensual (~35 min + ~1 h).** `--sufijo` manda todo a
archivos aparte para no mezclar las dos ventanas, y `--reusar-fichas` saltea los
anuncios cuya ficha ya se bajó (la ficha no depende de la ventana).

```powershell
python -u scrape_search.py --sufijo _mensual --checkin 2026-10-20 --checkout 2026-11-19 >> censo_mensual.log 2>&1
python -u scrape_pdp.py --sufijo _mensual --reusar-fichas pdp_raw.jsonl --checkin 2026-10-20 --checkout 2026-11-19 >> pdp_mensual.log 2>&1
python export_csv.py --sufijo _mensual
```

**Total: unas 10 horas**, casi todo en la etapa 2.

### Reglas que no hay que negociar

- **No bajar `polite_sleep()`** (1,2 a 2 s) ni paralelizar con hilos o async.
  El cuello de botella es deliberado: en ~23.000 requests no hubo un bloqueo.
- **No borrar los `.jsonl` ni `cells_pending*.json`** durante una corrida: son
  el checkpoint. `--reset` sólo para empezar de cero a propósito.
- **No cambiar la ventana de fechas a mitad del corrido.** Contamina el dataset
  de forma silenciosa e irreversible.
- **Si algo devuelve "sin estado embebido" repetidamente, parar.** Es un
  bloqueo, no un bug. No reintentar en loop ni cambiar el User-Agent: cortar y
  retomar más tarde, que el script reanuda solo.

### Diagnóstico de fallas conocidas

| síntoma | causa y arreglo |
|---|---|
| `ValidationError` en la etapa 2 | Airbnb cambió el hash de la persisted query. Abrir cualquier anuncio en el navegador con la pestaña de red abierta y copiar el hash de `/api/v3/StaysPdpSections/<hash>` a `PDP_HASH` en `scrape_pdp.py`. |
| Columnas de la ficha todas nulas | Cambió el nombre de una sección. Volcar `list(B.keys())` en `parse()` y comparar contra los nombres documentados. |
| `VALIDACION FALLIDA` en el export | Una columna clave cayó por debajo de su cobertura. Casi siempre es un cambio de estructura de Airbnb. |
| `typename de precio DESCONOCIDO` | Airbnb agregó un formato de precio. El aviso trae las claves exactas: agregar el caso en `parse_result()`. |
| `Permission denied` en algunos anuncios | El anuncio se dio de baja entre la etapa 1 y la 2. Normal: fueron 24 de 11.276. |
| `NO pude escribir <archivo>.csv` | El CSV está abierto en Excel. Cerrarlo y repetir el export. |
| Log del censo en 0 bytes | Falta el `-u`. |
| `UnicodeEncodeError` al imprimir | Falta `PYTHONIOENCODING=utf-8`. |

### Si hay que cambiar el parser después de relevar

Con el guardado de crudo activo (`pdp_full*.jsonl.gz`, `search_full*.jsonl.gz`),
no hay que volver a scrapear:

```powershell
python reparse.py
python reparse.py --sufijo _mensual
python export_csv.py
```

Deja `.bak` antes de sobrescribir. Verificado que reproduce el archivo original
byte por byte.

**Los CSV de este corte se relevaron antes de que existiera ese guardado**, así
que `reparse.py` no los alcanza: sus crudos no están en disco.

### Nota sobre los campos nuevos del parser

`scrape_pdp.py` y `scrape_search.py` producen **10 columnas que los CSV de este
corte no tienen**: `pct_5_estrellas` a `pct_1_estrella`, `percentil_calidad`,
`review_tags`, `es_favorito_huespedes`, `es_anuncio_nuevo`, `reviews_total`,
`rating_reviews`, `precio_desglose_txt`, `precio_total_exacto_txt` y
`precio_aviso`.

Se agregaron al parser después del relevamiento y poblarlas exigía volver a
scrapear. **Quien vuelva a correr el pipeline va a obtener esas columnas de
más: es lo esperado, no una inconsistencia del dataset.**
