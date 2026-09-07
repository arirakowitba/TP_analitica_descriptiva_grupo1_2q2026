# Airbnb CABA — hallazgos técnicos (2026-09-03, corregido 2026-09-05)

> Este documento se escribió ANTES de correr el pipeline. La corrida real
> está al final ("Corrida real end-to-end") y corrige tres cosas: el barrio,
> el precio y las secciones de la PDP. Ante duda, manda lo del final.

## Restricción de red
- El proxy de egress de la organización bloquea `airbnb.com`, `airbnb.com.ar`,
  `muscache.com` e `insideairbnb.com` DESDE el contenedor cloud de Claude Y
  desde el shell del sandbox de la app de escritorio.
- pypi.org SÍ pasa desde el sandbox.
- Conclusión: el scraper tiene que correr en tu Windows (VS Code, Python local),
  fuera del sandbox. Yo escribo el código, vos lo corrés.

## Descubrimiento clave: NO hace falta parsear HTML ni manejar Selenium
Tanto la página de búsqueda como la de cada anuncio embeben todo el JSON en:

    <script id="data-deferred-state-0">…</script>

Ruta dentro del JSON:
    j["niobeClientData"][0][1]["data"]["presentation"]["staysSearch"]

O sea: `requests.get(url)` + regex + `json.loads`. Sin navegador.

## API key pública (constante desde hace años)
    d306zoyjsyarp7ifhu67rjxn52tv0t20
Está en el HTML como `"api_config":{"key":"…","baseUrl":"/api"}`.

## Paginación — el cursor es construible, no hay que scrapearlo
El parámetro `cursor` de la URL es base64 de:
    {"section_offset":0,"items_offset":N,"version":1}
con N = 0, 18, 36, 54, … (18 resultados por página).

    import base64, json
    cursor = base64.b64encode(json.dumps(
        {"section_offset":0,"items_offset":n*18,"version":1},
        separators=(",",":")).encode()).decode()

## Techo de resultados y cómo saltearlo
- Máximo 15 páginas x 18 = ~270 anuncios por consulta. Confirmado.
- `results.paginationInfo.pageCursors` devuelve la cantidad REAL de páginas
  cuando está por debajo del tope. Ese es el criterio de corte del quadtree:
  si `len(pageCursors) == 15` => la celda está saturada, hay que subdividirla.
- La búsqueda acepta bounding box por URL (verificado, HTTP 200):

    https://www.airbnb.com.ar/s/homes
      ?refinement_paths%5B%5D=%2Fhomes
      &search_by_map=true&search_type=user_map_move
      &ne_lat=…&ne_lng=…&sw_lat=…&sw_lng=…&zoom=…
      &cursor=…

- Bbox de CABA: ne_lat=-34.5265 ne_lng=-58.3350 sw_lat=-34.7050 sw_lng=-58.5310
- Densidad medida: una celda de ~330m x 440m en Palermo ya devuelve ~100
  anuncios (6 páginas). Una de ~1.1km x 1.3km satura. El quadtree va a tener
  que bajar bastante en el corredor Palermo/Recoleta/Centro.

## Campos disponibles en cada resultado de búsqueda (etapa 1)
De `results.searchResults[i]`:
- `demandStayListing.id` -> base64; `atob()` da "DemandStayListing:<listing_id>"
- `demandStayListing.description.name.localizedStringWithTranslationPreference`
- `demandStayListing.location.coordinate.latitude` / `.longitude`
  (OJO: coordenadas ofuscadas por Airbnb, desplazamiento de hasta ~150 m)
- `title` -> ~~"Habitación compartida en San Nicolás" (tipo + barrio)~~
  YA NO: en modo mapa viene **null**. El barrio no viene más. Ver "Corrida
  real end-to-end (2026-09-05)" al final de este documento.
- `avgRatingLocalized` -> "4,9 (10)"  |  `avgRatingA11yLabel` -> texto completo
- `badges[].text` -> "Favorito entre huéspedes", "Superanfitrión"
- `structuredContent.primaryLine[]` -> "1 dormitorio", camas, huéspedes
- `structuredDisplayPrice.primaryLine` -> OJO, dos typenames con claves
  distintas (`price` vs `discountedPrice`+`originalPrice`). Ver el final.
  + `.qualifier` -> "por 5 noches"  (precio ATADO a las fechas de la consulta)
- `contextualPictures` -> array de fotos (cantidad + URLs)
- ~~`listingParamOverrides.checkin` / `.checkout`~~ YA NO: viene null.
También hay `mapResults.mapSearchResults` (20 por página) en paralelo.

## Etapa 2 — página de detalle (PDP)
    https://www.airbnb.com.ar/rooms/<listing_id>?adults=1&check_in=…&check_out=…
Mismo truco de `data-deferred-state-0`. Devuelve HTTP 200 con ~470 KB.

Oro puro, plano y listo para CSV, en:
    …presentation.stayProductDetailPage.sections.metadata
       .loggingContext.eventDataLogging
Campos: listingId, listingLat, listingLng, roomType, personCapacity, homeTier,
isSuperhost, visibleReviewCount, guestSatisfactionOverall, y las 7 dimensiones
de puntaje (accuracy, checkin, cleanliness, communication, location, value).

Y en `sections.metadata.sharingConfig`: propertyType, personCapacity,
reviewCount, starRating, imageUrl, y un `title` con el resumen
("Vivienda alquilada · Buenos Aires · ★4,76 · 1 dormitorio · 1 cama · 1,5 baños").

Secciones presentes en la PDP (contenido cargado en diferido, ver pendiente):
AMENITIES_DEFAULT, DESCRIPTION_DEFAULT, POLICIES_DEFAULT (reglas + noches
mínimas + cancelación), REVIEWS_DEFAULT, MEET_YOUR_HOST, LOCATION_PDP,
SLEEPING_ARRANGEMENT_IMAGES (sólo en algunos anuncios, ver el final),
PHOTO_TOUR_SCROLLABLE (todas las fotos),
AVAILABILITY_CALENDAR_DEFAULT (calendario -> ocupación), HIGHLIGHTS_DEFAULT.

## RESUELTO (2026-09-05)
El cuerpo de esas secciones NO viene en el HTML inicial: se pide después con
un POST a
    /api/v3/StaysPdpSections/f9c50b6a6918e94f6bf33d5163ec65afe0bb0715b72f2d41131d9256d3f785cb
Intenté reconstruir las `variables` a mano y devolvió ValidationError.
La forma exacta está en la clave del propio JSON embebido:
    j["niobeClientData"][0][0]
que es un string "StaysPdpSections:{…variables serializadas…}".
=> Próximo paso: leer esa clave de un HTML de PDP y copiar la estructura literal.

Hash de StaysSearch (por si se necesita el POST): 
    8e08ebd1763dbb6acc27501c6681549f4510067fad85ef4fd8ba38f2cda5b8fe

## Recordatorio de diseño
- El precio de Airbnb NO es un escalar: depende de fechas, noches y huéspedes,
  y no incluye fee de limpieza ni de servicio. Hay que fijar una ventana de
  fechas estándar para todo el corrido y documentarla.
- Inside Airbnb (corte 2026-07-24) sigue siendo complemento obligatorio:
  aporta calendario diario a 365 días y el histórico de reviews, que el
  scraper de búsqueda no da. Descarga manual desde el navegador:
  https://insideairbnb.com/get-the-data/

---

## RESUELTO — payload de StaysPdpSections (2026-09-05)
Las `variables` exactas se leen de `j["niobeClientData"][0][0]` (string
"StaysPdpSections:{…}"). Poniendo en `true` los flags `includeGp<X>Fragment`
del payload, TODA la ficha vuelve en UNA sola llamada POST. Verificado: 20
secciones con cuerpo, incluidas AMENITIES_DEFAULT (45 amenities con
`available` true/false, o sea también lo que el anuncio NO tiene),
POLICIES_DEFAULT (reglas, check-in/out, licencia), MEET_YOUR_HOST (nombre,
userId, superhost, reviews, rating, antigüedad, tasa de respuesta),
LOCATION_PDP, DESCRIPTION_DEFAULT, SLEEPING_ARRANGEMENT_IMAGES,
PHOTO_TOUR_SCROLLABLE (35 fotos).

Implementado en `scrape_pdp.py`. Ver README.md.

### Único punto abierto
`BOOK_IT_SIDEBAR.structuredDisplayPrice` vuelve null en la llamada armada a
mano — el desglose de precio con fees (limpieza, servicio) parece venir de otra
query. No es bloqueante: el precio total por la ventana de fechas SÍ viene en
los resultados de búsqueda (etapa 1), que es de donde lo toma el pipeline.

---

## Corrida real end-to-end (2026-09-05) — lo que cambió Airbnb desde el relevamiento

Primera ejecución contra Airbnb real. La arquitectura se confirmó entera (JSON
embebido, cursor construible, tope de 15 páginas, quadtree, payload de
StaysPdpSections con el hash vigente). Tres cosas ya no son como decía este
documento:

### 1. El barrio ya NO viene en los resultados de búsqueda
Antes: `title` -> "Habitación compartida en San Nicolás" (tipo + barrio).
Ahora, verificado en el mismo request:
- En **modo mapa** (`search_by_map=true&search_type=user_map_move`, el único que
  acepta bounding box): `title` y `subtitle` vuelven **null**. Probado también
  con `search_type=filter_change` sobre el mismo bbox: igual.
- Sacar `search_by_map` no es alternativa: cambia la forma del JSON y la clave
  `presentation.staysSearch` deja de existir.
- En **modo lista** (búsqueda por query, `/s/Palermo--Buenos-Aires.../homes`)
  `title` sí viene, pero ahora dice "Departamento en Buenos Aires": la **ciudad**,
  no el barrio. El `subtitle` trae el nombre del anuncio con pistas de zona,
  inconsistente ("Apartamento, Palermo Soho cerca de Jardín Botánico").
- La PDP tampoco lo trae: `LOCATION_PDP.subtitle` = "Buenos Aires, Buenos Aires,
  Argentina", `address` y `addressTitle` en null, `summaryLocationDetails` vacío,
  y `AVAILABILITY_CALENDAR.localizedLocation` = "Buenos Aires".

=> El barrio se deduce de las coordenadas. Implementado en `barrios.py`:
ray casting en Python puro contra el GeoJSON oficial de los 48 barrios
(`barrios_caba.geojson`, de data.buenosaires.gob.ar, CRS84). Sin dependencias
nuevas. Autotest con 10 puntos conocidos: 10/10. Recordar que las coordenadas
están desplazadas hasta ~150 m, así que sirve para agregar por barrio, no para
resolver un anuncio pegado a una avenida que hace de límite.

El tipo de propiedad sí se recupera, pero de la etapa 2: `roomType`
("Entire home/apt") y `sharingConfig.propertyType` ("Vivienda alquilada entero").

### 2. `structuredDisplayPrice.primaryLine` tiene DOS typenames, con claves distintas
Este era el bug caro: se perdía el precio de casi la mitad del censo.

| `__typename` | claves | frecuencia medida |
|---|---|---|
| `QualifiedDisplayPriceLine` | `price` | 21/38 |
| `DiscountedDisplayPriceLine` | `discountedPrice` + `originalPrice` | 17/38 |

Leer sólo `price` deja en null el ~45% de los anuncios. `scrape_search.py`
ahora cae a `discountedPrice` y guarda además `precio_original_txt` y
`precio_tipo`; `export_csv.py` deriva `precio_original_valor` y `descuento_pct`.

Formato de los strings: `'$\xa0220\xa0USD'` y `'por 5\xa0noches'`, con espacios
no separables (U+00A0). El parser de `export_csv.py` los tolera.

### 3. `listingParamOverrides` vuelve null
`checkin_consulta` / `checkout_consulta` salían vacíos. Ahora caen a la ventana
de la consulta, que es la que determinó el precio.

### 4. SLEEPING_ARRANGEMENT_IMAGES viene sólo en algunos anuncios
CORRECCIÓN (misma fecha, más datos): en un primer momento anoté acá que la
sección ya no existía, porque no aparecía en el anuncio que usé de sonda. Con
25 fichas bajadas, `arreglo_camas` viene poblado en 10 ("Dormitorio: 1 cama
queen, 1 cama de una plaza, 1 colchón en el suelo"). O sea: la sección existe y
depende del anuncio, no está muerta. Moraleja: no concluir "esta sección
desapareció" con una sola muestra.

De todos modos el dato de camas y baños siempre está en `detalle_items`
("Vivienda alquilada entero | 2 camas | 1 baño"), que viene en el 100%.

`host_tiempo_respuesta` sí parece muerto: `hostRespondTimeCopy` viene null en
las 25, pero la info está en `host_detalles` ("Responde en menos de una hora").

### Lo que sí funcionó tal cual está documentado
- `PDP_HASH` vigente, sin `ValidationError`. 23 secciones con cuerpo.
- `AMENITIES_DEFAULT`: 36 a 47 amenities por anuncio, con `available` true/false
  y 13 grupos (incluido "No incluidos").
- `eventDataLogging`: las 7 dimensiones de rating, `personCapacity`,
  `isSuperhost`, `visibleReviewCount`, coordenadas y
  `mapMarkerRadiusInMeters` = 152 (confirma el desplazamiento de ~150 m).
- `POLICIES_DEFAULT.houseRulesSections`: "Check-in y check-out" y
  "Durante tu estadía". `additionalHouseRules` y `propertyLicenseTextList`
  existen como claves y vienen null en los anuncios probados: es esperable,
  no todos los tienen.
- El quadtree parte bien: el bbox completo satura (15 páginas) y las celdas del
  sur entran en 0 o 1 página.
- `BOOK_IT_SIDEBAR.structuredDisplayPrice` sigue en null. Punto abierto sin
  cambios; no es bloqueante.

### Nota operativa: el log del censo necesita `-u`
`python scrape_search.py > censo.log 2>&1` deja el log en 0 bytes durante
horas: cuando stdout no es una consola, Python lo bufferiza por bloques. Para
poder monitorear hay que correrlo con `python -u`.

### 5. Censo completo: 11.276 anuncios, y qué significa ese número
Corrida del 2026-09-05, ventana 2026-10-20 a 2026-10-25, 2 huéspedes: 147
celdas, 11.276 anuncios únicos, **cero bloqueos**, cola vacía (o sea: todas
las celdas hoja informaron menos de 15 páginas, que es el criterio de
completitud que da Airbnb, no una estimación nuestra).

11.276 es bastante menos que los ~25-30k que reporta Inside Airbnb para CABA,
y no es que falte cobertura: la búsqueda sólo devuelve anuncios **disponibles
para esa ventana de fechas y para 2 huéspedes**. Quedan afuera los bloqueados,
los que tienen mínimo de noches incompatible y los de capacidad 1. El censo es
"oferta disponible en la ventana", no "universo de anuncios". Para el universo
hace falta Inside Airbnb.

### 6. Hay precios que no son precios (0,9% del censo)
107 de 11.276 anuncios dan más de 1.000 USD por noche, con casos de 89.012 USD.
No es un error de parseo: el desglose crudo de Airbnb dice textual
`"5 noches por $ 89.011,81 USD"` -> `"$ 445.059,03 USD"`. Son casi con
seguridad anfitriones que bloquean el calendario poniendo un precio impagable
en vez de cerrar las fechas.

Impacto: arruinan cualquier promedio. Con ellos adentro la media da 211 USD y
el desvío 2.234; sin ellos, media 106 y desvío 94 (mediana 79 en los dos
casos — la mediana es inmune).

`export_csv.py` los marca en la columna `precio_sospechoso`
(`precio_por_noche > UMBRAL_PRECIO_NOCHE`, 1.000 USD) y NO los borra: la
decisión de filtrarlos es del análisis, no del scraper.

### 7. La etapa 2 se caía ante un corte de TCP (arreglado)
Primera corrida larga: murió a las 2.984 fichas con
`ConnectionResetError(10054)`. No era un bloqueo — sondeado inmediatamente
después, Airbnb respondía normal (3 de 3, 1,1 a 1,5 s, 23-24 secciones con
cuerpo) — sino un agujero del código: `fetch_pdp()` miraba códigos HTTP (429,
5xx) pero no atrapaba excepciones de red, así que cualquier corte de conexión
salía como excepción y se llevaba puesto el proceso entero. `get_deferred_state()`
(etapa 1) sí las atrapaba, y por eso el censo aguantó 147 celdas sin problemas.

Arreglado: `fetch_pdp()` ahora atrapa `requests.RequestException` con backoff
exponencial, y además trata una respuesta que no sea JSON como fallo en vez de
excepción. Esto último importa por una razón de diseño: un desafío de bot ahora
cuenta para el corte por errores encadenados (`fallos >= 15`), que es
exactamente el comportamiento que se busca ante un bloqueo real.

Nota operativa: sobre corridas de horas hay que asumir que la conexión se corta
sola alguna vez. No es señal de nada; el pipeline tiene que sobrevivirlo.

### 8. Resultado final de la corrida (2026-09-05)
Etapa 1: 11.276 anuncios, 147 celdas, 0 bloqueos, ~35 min.
Etapa 2: 11.252 fichas (99,8%), 416.435 filas de amenities, ~8 h.
Errores en toda la etapa 2: 24 anuncios con `Permission denied` (dados de baja
entre una etapa y la otra) y 1 corte de red recuperado. Cero señales de bloqueo
en ~11.300 requests: el `PDP_HASH` y la `API_KEY` aguantaron toda la corrida.

Amenities: 3.362 nombres distintos en 11.248 anuncios, con cola larguísima
porque el anfitrión escribe el detalle. El export pivotea sólo los que están en
>= 1% (169 columnas) y agrega 30 columnas `fam_*` agrupadas por concepto; la
tabla larga completa queda en `airbnb_caba_amenities.csv`.

OJO al leer los amenities: Airbnb lista también lo que el anuncio NO tiene
(`available: false`). Por eso "Detector de humo" aparece mencionado en el 100%
de los anuncios pero sólo el 25% lo tiene de verdad. Las columnas `fam_*`
cuentan disponibilidad real; las `am_*` traen True/False/vacío.

Concentración de la oferta: 5.592 anfitriones para 11.247 anuncios. 4.297 tienen
un solo anuncio, pero 143 tienen 10 o más y el mayor opera 137. O sea que hay
un núcleo profesionalizado que conviene separar en cualquier análisis.

---

## Serie MENSUAL (2026-09-06)

Segundo relevamiento, ventana 2026-10-20 a 2026-11-19 (30 noches, 2 huéspedes).
Mismo día de inicio que la serie de 5 noches, para que compartan estacionalidad.

### Con 30+ noches Airbnb cambia el formato del precio
    5 noches  -> "$ 204 USD"    qualifier: "por 5 noches"
    30 noches -> "$ 1.156 USD"  qualifier: "mensual"
El qualifier no trae número, así que `parse_noches()` devolvía null y se perdía
todo el precio. Ahora reconoce "mensual" (=30 noches) y el export deja la
columna `precio_regimen` con `mensual` / `por_noche`.

Ese precio mensual YA tiene aplicado el descuento por estadía larga: no es el
precio de 5 noches por 6.

### Cada ventana es una serie aparte, en archivos aparte
Los scripts aceptan `--sufijo`. La serie mensual vive en
`search_raw_mensual.jsonl`, `pdp_raw_mensual.jsonl`,
`airbnb_caba_listings_mensual.csv`, etc. Sin eso, el segundo censo escribía
sobre los mismos `.jsonl` y mezclaba dos regímenes de precio en el mismo
archivo, sin ninguna marca que permitiera separarlos después.

### La ficha no depende de la ventana: se reusa
`scrape_pdp.py --reusar-fichas pdp_raw.jsonl` saltea los anuncios ya bajados.
De los 10.369 anuncios mensuales, 8.861 ya tenían ficha: sólo se bajaron 1.508
(1 hora en vez de 7). El export lee las dos fuentes de fichas y concatena.

### El mínimo de noches se puede INFERIR cruzando las dos series
Airbnb no expone el mínimo de noches en `StaysPdpSections` (sale de
`PdpAvailabilityCalendar`, otra query, hash no encontrado). Pero comparar los
dos censos lo aproxima gratis: un anuncio que cotiza 30 noches y NO aparece
cotizando 5 no acepta estadías cortas. Columnas `solo_larga_estadia` y
`acepta_corta_estadia` (serie mensual), `acepta_larga_estadia` (serie corta).

### Resultados
Censo: 10.369 anuncios, 153 celdas, 0 bloqueos, ~50 min.
Etapa 2: 1.508 fichas nuevas, 0 errores de cualquier tipo.
Cobertura: precio 100%, capacidad/host/tipo 100%, dormitorios 99,9%,
baños 99,6%, barrio 99,1%, rating 83% (el resto son anuncios sin reviews).

Precio mensual (sin sospechosos): mediana USD 1.783, p25 1.337, p75 2.664.

Descuento por estadía larga, sobre los 8.766 anuncios que están en las dos
series: mediana USD/noche pasa de 79,0 a 60,6, o sea **22,3% de descuento**
(p25 12,8%, p75 30,3%). El 95% de los anuncios baja el precio por mes.

Larga estadía pura (1.500 anuncios que NO aceptan 5 noches): más baratos
(USD 1.551 vs 1.823 de mediana mensual) y con menos superhosts (27% vs 38%).
Es un segmento distinto, más parecido a alquiler residencial que a temporario.

---

## Mejoras a la base cruda (2026-09-06)

### 1. Se guarda la respuesta cruda comprimida
El problema estructural del pipeline era que los `.jsonl` guardaban el registro
YA PARSEADO. Cada campo descubierto tarde exigía volver a scrapear: pasó con el
precio con descuento (hubo que hacer `--reset` y perder el trabajo hecho), con
los agregados de reviews y con el desglose del precio.

Ahora `scrape_pdp.py` escribe `pdp_full.jsonl.gz` y `scrape_search.py` escribe
`search_full.jsonl.gz`: gzip multi-miembro, una línea JSON por registro (cada
append abre un miembro nuevo y `gzip.open()` los concatena de forma
transparente al leer). Medido: 28 KB por ficha, ~315 MB para las 11.252.
Se puede desactivar con `--sin-crudo`.

`reparse.py` re-parsea desde ahí sin red. Verificado: el re-parseo reproduce
el `pdp_raw.jsonl` original **byte por byte** (mismo MD5). Deja `.bak` antes de
sobrescribir.

Consecuencia práctica: mejorar el parser pasó de ser 8 horas de re-scrapeo a
ser minutos de CPU.

### 2. Campos que ya bajábamos y tirábamos
De `REVIEWS_DEFAULT`, sección que siempre venía en la respuesta:
- `pct_5_estrellas` a `pct_1_estrella`: el reparto de estrellas, no sólo el
  promedio. Distingue un 4,9 sólido de un 4,9 con dos reseñas malas.
- `percentil_calidad`: el percentil que calcula Airbnb ("top 5%", "top 10%").
  OJO: sólo lo asigna a los mejores anuncios, viene null en la mayoría.
- `review_tags`: tags con conteo, sintetizados por Airbnb de lo que mencionan
  los huéspedes ("Ubicación:15 | Confort:8 | Calidad del sueño:6").
- `es_favorito_huespedes`, `es_anuncio_nuevo`, `reviews_total`, `rating_reviews`.

El TEXTO de las reseñas NO viene (`reviewsData.reviews` = 0): eso es otra query.

De `structuredDisplayPrice.explanationData` en la búsqueda:
- `precio_desglose_txt`: el precio unitario CON centavos ("5 noches por
  $ 36,00 USD"). El precio por noche se venía calculando dividiendo el total
  ya redondeado, que arrastra error.
- `precio_total_exacto_txt`: el total con centavos.
- `precio_aviso`: aviso de baja reciente de precio ("Hace poco, X bajó el
  precio para estas fechas, con respecto a la tarifa promedio de las últimas
  60 noches"). Señal de presión competitiva por anuncio.

### Lo que NO se puede recuperar sin re-scrapear
Los datos ya bajados se parsearon antes de que existiera el guardado de crudo,
así que `reparse.py` no los alcanza. Los campos nuevos requieren:
- de la ficha (reviews): re-correr la etapa 2, ~8 h.
- de la búsqueda (desglose de precio): re-correr el censo, ~50 min por serie,
  pero eso genera OTRA foto de disponibilidad, no la misma.
De acá en adelante ninguna mejora del parser va a necesitar esto.

### 3. Guardas contra la falla silenciosa (2026-09-06)
El bug del precio no tiró ningún error: dejó el 32% de las filas en null y lo
encontré de casualidad mirando un `describe()`. En la serie mensual habría sido
el 92%, porque con ventana de 30 noches casi todo anuncio aplica descuento y
cae en el typename que el parser no leía. Esa es la falla peligrosa de este
pipeline: no rompe, produce un dataset incompleto que parece completo.

Dos guardas:

**En `scrape_search.py`**: la lista `PRECIO_CONOCIDOS` con los typenames que el
parser sabe leer. Si aparece uno nuevo, o si un precio no se pudo leer, se
acumula en `AVISOS` y la corrida termina gritándolo con las claves exactas que
trajo la estructura desconocida (que es lo que hace falta para arreglar el
parser). Probado con un typename inventado.

**En `export_csv.py`**: `validar()` compara la cobertura de 16 columnas clave
contra un piso esperado (`COBERTURA_MINIMA`). Probado reproduciendo el bug
viejo sobre el dataset real: detecta las 4 columnas caídas y las lista con la
cobertura real vs la esperada.

Los pisos tienen en cuenta los nulos legítimos: `barrio` 90% (los anuncios de
GBA que entran por el margen del bbox), `rating_general` 70% (los anuncios sin
reviews).
