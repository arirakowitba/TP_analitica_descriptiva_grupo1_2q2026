# Corte de datos — Airbnb CABA

**Fecha del relevamiento: 5 y 6 de septiembre de 2026.**
Este es el corte cerrado del proyecto. No se agregan más relevamientos.

## Los dos datasets

Son dos series, la misma ciudad relevada con dos plazos de estadía distintos.
**No se pueden mezclar**: el precio de Airbnb es función de la ventana de fechas,
así que cada serie es una unidad de precio distinta.

| | serie corta | serie mensual |
|---|---|---|
| ventana cotizada | 2026-10-20 a 2026-10-25 (5 noches) | 2026-10-20 a 2026-11-19 (30 noches) |
| huéspedes | 2 | 2 |
| anuncios | 11.276 | 10.369 |
| con ficha completa | 11.252 (99,8%) | 10.369 (100%) |
| precio mediano | USD 79 / noche | USD 1.783 / mes (60,6 / noche) |
| viviendas enteras | 10.326 | 9.596 |

## Archivos y checksums

| archivo | filas | columnas | tamaño | MD5 |
|---|---|---|---|---|
| `airbnb_caba_listings.csv` | 11.276 | 287 | 37.7 MB | `ee081dc32c6c7c8469fa289591584bba` |
| `airbnb_caba_normalizado.csv` | 10.326 | 59 | 19.3 MB | `1cd27f30a9a31cf4183626c486c967a8` |
| `airbnb_caba_amenities.csv` | 416.395 | 6 | 37.1 MB | `53a33fb9c95fb313997e14a52fa0357d` |
| `airbnb_caba_listings_mensual.csv` | 10.369 | 288 | 34.2 MB | `8e6ca88427719cc195a4477dd2c4602d` |
| `airbnb_caba_normalizado_mensual.csv` | 9.596 | 60 | 17.4 MB | `4edeaee854820ec8a59bcd0bd9f9c321` |
| `airbnb_caba_amenities_mensual.csv` | 466.706 | 6 | 41.6 MB | `b51a2d1b2ccf8b4c3d17c2f3fb10f940` |

Verificar en Windows: `certutil -hashfile <archivo> MD5`

## Por dónde empezar

`airbnb_caba_normalizado.csv` y su par mensual: son las viviendas enteras con el
vocabulario de un portal inmobiliario (`dormitorios`, `banios`, `precio`,
`barrio`), listas para analizar o cruzar. Los `listings` traen todo, incluidas
las 169 columnas de amenities. Los `amenities` son la tabla larga completa.

## Lo que hay que saber antes de usarlo

**El precio no es un atributo del inmueble.** Depende de la ventana de fechas,
las noches y los huéspedes, y NO incluye fee de limpieza ni de servicio (el
costo real al huésped es 15-25% mayor). Comparable dentro de cada serie y con
nada más.

**Filtrar `precio_sospechoso` antes de promediar.** 107 anuncios de la serie
corta informan más de USD 1.000 por noche, con un máximo de 89.012. No es un
error de parseo: son anfitriones que bloquean el calendario con un precio
impagable. Con ellos adentro la media da 211 USD y el desvío 2.234; sin ellos,
106 y 94. La mediana (79) no se mueve.

**El censo es oferta disponible, no el padrón de anuncios.** La búsqueda sólo
devuelve lo que acepta esa estadía. Inside Airbnb reporta 25-30k anuncios en
CABA; acá hay 11.276 porque el resto estaba ocupado, exigía otro mínimo de
noches o no entra con 2 huéspedes.

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

`barrio` nulo significa fuera de CABA: 95 anuncios que entran por el margen del
bounding box.
Una salvedad sobre la interpretación: lo **medido** es la distribución de
`radio_ofuscacion_m` y la cantidad de decimales de cada coordenada. Que los de
radio 0 tengan la coordenada real (sólo redondeada) y los de radio 152 la tengan
desplazada es la lectura más razonable de ese patrón, pero **no se pudo
verificar**: haría falta la dirección real de algún anuncio para comparar, y
Airbnb no la da. Tratar el radio como una cota superior del error, no como una
medición del error.


**Los amenities `am_*` traen True/False/vacío, y el False es dato real**: Airbnb
lista explícitamente lo que el anuncio NO tiene. Por eso "Detector de humo"
aparece mencionado en el 100% de los anuncios pero sólo el 25% lo tiene. Para
analizar, usar las columnas `fam_*`, que cuentan disponibilidad real.

**Una fila es una publicación, no una propiedad.** 92% son unidades enteras,
pero hay 516 habitaciones privadas (varias pueden ser del mismo departamento) y
391 alojamientos hoteleros. La columna `categoria_alojamiento` los separa; los
`normalizado` ya vienen filtrados a `vivienda_entera`.

### Prueba de sensibilidad: el desplazamiento NO afecta el análisis por barrio

El análisis del proyecto es a nivel barrio y comuna, así que la pregunta
relevante no es cuán exacta es cada coordenada, sino si el desplazamiento
cambia las conclusiones agregadas. Se midió.

Se calculó la distancia de cada anuncio al límite de su barrio y se marcaron
como dudosos los que están más cerca del límite que su propio radio de error:
1.694 anuncios, el 15,2% del dataset (27,7% de los de radio 152 m y 78,0% de
los de radio 500 m). Después se recalcularon los agregados sin ellos.

Resultado sobre los 17 barrios con 100 o más anuncios:

- Cambio máximo en la mediana de precio: **4,9%**. Mediana del cambio: 0,9%.
- Barrios donde la mediana se mueve más de 5%: **0 de 17**.
- El ranking de barrios por volumen queda **idéntico y en el mismo orden**.

La razón es que el desplazamiento de Airbnb es aleatorio en dirección: sobre
cientos de anuncios por barrio, los que se corren para un lado compensan a los
que se corren para el otro. Es ruido, no sesgo.

Conclusión: para agregados por barrio y comuna el dataset se usa completo, sin
filtrar por precisión. La salvedad queda para un análisis a nivel unidad
(distancia a un subte, micromercados sub-barrio), donde habría que usar sólo
los 5.840 anuncios con `mapMarkerType = EXACT` (`radio_ofuscacion_m == 0`), que
son una muestra pareja: entre 39% y 58% por barrio, desvío de 4,4 puntos.

## Lo que este dataset NO tiene

Metros cuadrados, dirección exacta, expensas y antigüedad: no existen del lado
de Airbnb. Por eso un cruce con ZonaProp es **a nivel barrio, no a nivel
unidad**, y no hay precio por m².

Tampoco tiene el mínimo de noches exacto, el calendario de disponibilidad a 365
días ni el texto de las reseñas: eso está en Inside Airbnb (descarga manual).
El mínimo de noches se aproxima con las columnas `solo_larga_estadia` /
`acepta_corta_estadia`, que salen de cruzar las dos series.

## Aviso sobre el código

`scrape_pdp.py` y `scrape_search.py` producen **10 columnas que estos CSV no
tienen**: `pct_5_estrellas` a `pct_1_estrella`, `percentil_calidad`,
`review_tags`, `es_favorito_huespedes`, `es_anuncio_nuevo`, `reviews_total`,
`rating_reviews`, `precio_desglose_txt`, `precio_total_exacto_txt` y
`precio_aviso`.

Se agregaron al parser DESPUÉS de este relevamiento y poblarlas exigía volver a
scrapear, que quedó fuera de alcance por la fecha de entrega. Si alguien vuelve
a correr el pipeline va a obtener esas columnas de más: es lo esperado, no una
inconsistencia del dataset.

## Datos personales

Los `listings` incluyen `host_nombre`, `host_sobre_mi` (biografías escritas por
los anfitriones), `descripcion` y `host_id`: son datos personales de unos 5.600
anfitriones identificables. Tratar en consecuencia y no publicar sin depurar.
