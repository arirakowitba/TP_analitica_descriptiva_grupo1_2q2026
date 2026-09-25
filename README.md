# Análisis inmobiliario y habitacional en la Ciudad de Buenos Aires

| Ariel Rakowsczyk        | 66828 |
|-------------------------|-------|
| Gaetano Murchio         | 66539 |
| Juan Cruz Moyano        | 65880 |
| Miranda Contieri Quiles | 67125 |

Analítica Descriptiva

2Q 2026

# 0 Organización del repositorio

El repositorio sigue una estructura orientada a trazabilidad del proceso KDD: los datos crudos se conservan sin modificaciones, las transformaciones se documentan por separado y los datasets procesados se guardan como salidas reproducibles.

```text
.
├── data/
│   ├── raw/                 # datos crudos obtenidos por scraping o descarga
│   └── processed/           # datasets limpios o consolidados para analisis
├── docs/                    # documentacion tecnica y metodologica
├── Fuentes_de_enriquecimiento/
│   └── datasets_contextuales_caba.py
├── notebooks/               # notebooks de calidad, limpieza y EDA
├── scrappers/               # scripts de extraccion por fuente
├── src/                     # funciones reutilizables para notebooks
├── requirements.txt
└── README.md
```

Los archivos en `data/raw` no deben editarse manualmente. Cualquier limpieza, union, imputacion, filtrado o normalizacion debe generar una nueva salida en `data/processed`, manteniendo documentada la decision aplicada.

La documentacion general de los scrapers se encuentra en `docs/scrapers.md`. La extraccion de Airbnb, por su complejidad tecnica, cuenta ademas con una documentacion especifica en `docs/scraper_airbnb.md`.

## 0.1 Reproduccion del entorno

Para preparar el entorno de trabajo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En Windows, la activacion del entorno puede realizarse con:

```bash
.venv\Scripts\activate
```

Los scripts principales aceptan `--help` para revisar parametros, rutas de salida y limites de ejecucion:

```bash
python scrappers/scraper_mercadolibre_ventas.py --help
python scrappers/scraper_meli_alquileres_ampliado.py --help
python scrappers/scraper_argenprop_inmuebles.py --help
python scrappers/scraper_zonaprop_inmuebles.py --help
```

## 0.2 Estado actual de avance

- Repositorio inicial organizado con datos crudos, scripts de extraccion y documentacion tecnica.
- Fuentes principales relevadas: Mercado Libre, Airbnb, ZonaProp y ArgenProp.
- Fuentes de enriquecimiento identificadas: transporte, salud, educacion, cultura, espacios verdes, gastronomia turistica, censo y geometrias oficiales.
- Pendiente para la PreEntrega 2: construccion de notebooks de calidad y limpieza, dataset procesado, diccionario de datos, EDA inicial e interpretacion de hallazgos.

# 1 Caso de negocio

## 1.1 Introducción

El mercado inmobiliario de la Ciudad de Buenos Aires se caracteriza por ser remarcablemente activo, dinámico, e incierto. Durante el período de 2025, el alquiler de vivienda representó un 36% de los hogares totales del distrito, junto con un 52% de hogares propietarios, y el restante 12% compuesto por diversas situaciones precarias e informales (1). Esto implica que las condiciones macroeconómicas en cuanto a nivel de precios y desarrollo, así como las tendencias en demografía, crecimiento urbano, y turismo, pueden incidir en una amplia proporción de las unidades habitacionales porteñas.

La estructura del mercado debe interpretarse a la luz de distintas condiciones económicas y regulatorias. Por un lado, el crédito hipotecario tuvo históricamente una participación reducida, aunque mostró una recuperación durante 2024-2025. Incluso en ese contexto, una parte importante de las compraventas continúa realizándose sin financiamiento hipotecario. Esto restringe el acceso a la compra a los hogares que disponen de ahorro previo, ingresos suficientes o capital propio, y mantiene al alquiler como principal alternativa de acceso a la vivienda para una parte relevante de la población.

Por otro lado, el marco regulatorio de los alquileres cambió sustancialmente, y puede haber modificado los incentivos de propietarios e inquilinos. La flexibilización contractual, luego de la derogación de la ley de alquileres en 2023, es uno de los motivos del aumento en la oferta publicada de departamentos en alquiler en AMBA, según un informe oficial de la Unidad de Evaluación de Impacto (2).

También existe legislación específica sobre el alquiler temporario. La Ley 6.255 de la Ciudad establece un Registro de Propiedades de Alquileres Temporarios Turísticos y obligaciones para quienes ofrecen este tipo de alojamiento. Este marco puede modificar los costos y los incentivos de los propietarios al elegir entre alquiler permanente y temporario. Sin embargo, dado que el trabajo utiliza un corte transversal, no se atribuirán directamente a la regulación las diferencias observadas entre modalidades.

Todas estas medidas de contexto económico muestran que el mismo patrón observado puede tener distintas explicaciones y, por lo tanto, distintas respuestas de política pública.

Comprender el impacto de estos factores urbanos en el mercado resulta importante para la gestión del espacio y servicios públicos, así como la del desarrollo inmobiliario privado. La Ciudad cuenta con 1,6 millones de viviendas, y su distribución y destino presentan una variedad especialmente rica en detalles e incertidumbre, siendo sujeto de un análisis multidimensional (3). La variedad de operaciones - compra, alquiler convencional, y alquiler temporal - produce una tensión económica y urbana, en cuanto al uso del recurso limitado de la vivienda, el espacio, y los servicios públicos. Así, se plantea la necesidad de explorar tendencias en este mercado que aclaren su funcionamiento, de manera unificada y multivariada.

A lo largo de este análisis, se recopilarán fuentes de publicaciones para venta y alquiler de viviendas de diferentes portales web, con sus atributos principales. Se intentará contrastar los diferentes factores urbanos con tendencias no solo a nivel precio, sino también en cuanto a tipo de operación solicitada, competitividad, y diseño habitacional. Se busca esclarecer el funcionamiento del mercado inmobiliario y producir insights accionables para el trabajo de reguladores y organismos públicos dedicados al desarrollo urbano, ponderando los beneficios económicos y sociales.

En particular, el Instituto de Vivienda de la Ciudad es el encargado de realizar análisis de disponibilidad, calidad, distribución, y tendencias a nivel hogares en Buenos Aires, así como elevar recomendaciones y desarrollar políticas de viviendas para el ejecutivo, en conjunto con áreas como Turismo y Planeamiento Urbano. Este organismo tiene la responsabilidad de detectar potenciales desequilibrios en el tejido urbano, y tiene a su disposición datos poblacionales y de la administración pública. Para el desarrollo del trabajo, nos ubicamos en el rol de esta institución, cuya tarea requiere **identificar en qué zonas la composición de la oferta inmobiliaria presenta posibles desequilibrios respecto de las necesidades habitacionales, las características demográficas y la disponibilidad de servicios urbanos.**

Al tratarse de un organismo estatal, se tiene como principal objetivo el beneficio social en su conjunto, ponderando equilibrio urbano, desarrollo, y acceso a vivienda, no exclusivamente la rentabilidad económica.

## 1.2 Definición operativa del problema

En este trabajo se denominará **desajuste territorial de la oferta habitacional** a una diferencia observable entre la composición de las publicaciones residenciales de una zona y una o más de las siguientes dimensiones: la estructura demográfica y habitacional de su población, la disponibilidad relativa de alquiler permanente, la concentración de alquiler temporario y el acceso a transporte y servicios urbanos.

El concepto no supone que las publicaciones representen la totalidad del stock de viviendas ni permite afirmar, por sí solo, la existencia de déficit habitacional, demanda insatisfecha, desplazamiento de residentes o sustitución de alquiler permanente por temporario. Las publicaciones se utilizarán como evidencia de la **oferta publicada** durante el período relevado. En consecuencia, los resultados permitirán detectar asociaciones, brechas y zonas que ameriten análisis o intervención prioritaria, pero no demostrar relaciones causales.

El desajuste se analizará inicialmente mediante dimensiones separadas, sin combinarlas de antemano en un único índice:

- **Adecuación tipológica:** relación entre la composición de los hogares y la participación de las distintas tipologías ofrecidas.
- **Disponibilidad residencial publicada:** cantidad de publicaciones de alquiler permanente en relación con la población, los hogares o el stock de viviendas de la zona, según la granularidad disponible.
- **Presión potencial del alquiler temporario:** densidad y participación de alojamientos temporarios completos respecto del stock habitacional y de la oferta residencial publicada.
- **Accesibilidad urbana:** disponibilidad o proximidad de transporte y servicios relevantes para las viviendas y la población de cada zona.

## 1.3 Decisiones públicas que busca informar

El análisis se concentrará en producir evidencia para tres decisiones del Instituto de Vivienda de la Ciudad:

1. **Priorizar zonas para ampliar o fortalecer la oferta de alquiler permanente.** Se identificarán áreas con baja disponibilidad residencial publicada o con una composición de tipologías poco alineada con el perfil de sus hogares.
2. **Priorizar zonas para monitorear la concentración del alquiler temporario.** Se señalarán barrios donde la densidad de alojamientos temporarios completos coincida con una baja disponibilidad relativa de alquiler permanente o con precios residenciales elevados. Esta coincidencia se interpretará como una señal para profundizar el diagnóstico, no como evidencia automática de desplazamiento.
3. **Priorizar intervenciones habitacionales o de accesibilidad urbana.** Se buscarán zonas en las que los desajustes de oferta coincidan con menor acceso a transporte o servicios, distinguiendo si la respuesta pertinente corresponde a vivienda, infraestructura, regulación, fiscalización o producción de información adicional.

Una zona será considerada prioritaria cuando combine una brecha de magnitud relevante, una cantidad suficiente de población potencialmente afectada y evidencia basada en un número mínimo de observaciones. Los umbrales definitivos se establecerán después del EDA, para evitar fijar reglas incompatibles con la distribución y calidad real de los datos.

## 1.4 Objetivos generales

- Medir la distribución territorial de las tres modalidades de operación.

- Comparar precios y características de los inmuebles entre barrios y modalidades.

- Analizar la relación entre el perfil demográfico de cada zona y su composición inmobiliaria.

- Evaluar si la disponibilidad y proximidad de servicios urbanos se relacionan con los precios y la concentración de la oferta.

- Construir indicadores sintéticos de accesibilidad, presión turística y disponibilidad habitacional.

- Segmentar barrios o micromercados según sus características demográficas, urbanas e inmobiliarias.

- Identificar zonas prioritarias para políticas de vivienda, infraestructura o regulación del alquiler temporal.

## 1.5 Preguntas de análisis

**Nivel descriptivo: características de la oferta publicada**

¿Cómo se distribuyen los tres tipos de operaciones en los diferentes barrios y comunas?

¿Qué precios, tipologías, u otras características predominan en cada operación?

¿Cómo se distribuyen los servicios urbanos, el transporte, los atractivos turísticos y las principales características demográficas?

**Nivel diagnóstico: explicación de patrones observados**

¿Cómo se relacionan la composición demográfica, la centralidad, los servicios públicos y otros atributos urbanos con la distribución territorial de las operaciones?

¿En qué medida la composición demográfica se relaciona con las tipologías residenciales ofrecidas en cada zona?

¿Las brechas territoriales de precio y composición de la oferta se mantienen al comparar propiedades y zonas semejantes?

**Nivel predictivo: estimaciones en función de las variables**

¿Cómo puede estimarse el precio publicado de un inmueble dentro de cada modalidad a partir de sus características, modalidad de operación, ubicación y entorno urbano?

¿Qué distribución de operaciones puede estimarse en una zona según sus características actuales demográficas, turísticas y de accesibilidad?

**Nivel prescriptivo: insights orientados a decisiones**

¿Qué zonas deberían priorizarse para fortalecer la oferta de alquiler permanente, monitorear la concentración del alquiler temporario o mejorar la accesibilidad urbana?

¿Qué indicadores debería monitorear el Instituto de Vivienda para detectar posibles desequilibrios entre alquiler temporal, alquiler permanente y necesidades habitacionales?

¿Qué alternativa de intervención resulta más adecuada para cada tipo de desajuste, considerando la magnitud de la brecha, la población potencialmente afectada, la calidad de la evidencia y las competencias del organismo?

## 1.6 Frontera operativa

El análisis comprende publicaciones de inmuebles residenciales ubicados dentro de la Ciudad Autónoma de Buenos Aires, obtenidas de Mercado Libre, ZonaProp, ArgenProp y Airbnb durante la etapa de extracción realizada entre agosto y septiembre de 2026. Se adopta un diseño de corte transversal: el objetivo es caracterizar la oferta disponible en el momento del relevamiento y no estudiar su evolución histórica.

La unidad de análisis será la publicación inmobiliaria activa en cada portal y fecha de consulta. Los registros representan oferta publicada y no necesariamente viviendas únicas, operaciones concretadas ni oferta efectiva de inmuebles. Se analizarán tres modalidades de operación: venta, alquiler permanente y alquiler temporal. Para favorecer su comparabilidad, se incluirán únicamente inmuebles destinados a uso habitacional, principalmente departamentos, casas y PH. Se excluirán cocheras, oficinas, locales comerciales, terrenos y otras propiedades sin destino residencial. En Airbnb, el análisis comparativo utilizará exclusivamente alojamientos completos, dejando fuera habitaciones privadas, habitaciones compartidas y establecimientos hoteleros.

El alcance geográfico será la totalidad de CABA. El barrio se utilizará como nivel principal para describir precios, tipologías, servicios y composición de la oferta cuando la localización lo permita. La comuna será empleada como unidad complementaria y como nivel común de integración con aquellas fuentes demográficas que no posean información desagregada por barrio.

En Airbnb, los precios corresponden a consultas realizadas para dos huéspedes y con fecha de inicio el 20 de octubre de 2026, utilizando ventanas comparables de cinco y treinta noches. Estos valores representan precios ofrecidos para condiciones de búsqueda específicas y no precios promedio históricos del alojamiento.

El estudio analizará precios publicados, características de los inmuebles, composición territorial de la oferta y su relación con variables demográficas y de entorno urbano. No se estimarán rentabilidades financieras ni se estudiarán operaciones inmobiliarias efectivamente realizadas. Debido a su naturaleza observacional y transversal, los resultados permitirán identificar asociaciones, brechas y patrones territoriales, pero no establecer por sí solos relaciones causales.

## 1.7 Hoja de ruta

| **Tarea**                                  | **Semana**       | **Descripción**                                                                                                                                                       |
|--------------------------------------------|------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Definición del problema                    | 10 de agosto     | Planteo de posibles casos de negocio, preguntas de interés, limitaciones, factor diferencial.                                                                         |
| Planteo de objetivos                       | 17 de agosto     | Profundidad del análisis, definición del interlocutor, investigación de disponibilidad de fuentes primarias y secundarias, prueba de concepto.                        |
| Extracción de datos                        | 24 de agosto     | Scrapeo y consultas de APIs, ejecución de la extracción, definición de columnas clave.                                                                                |
| Reformulación iterativa                    | 31 de agosto     | Desarrollo de los objetivos según la data disponible, reformulación y extracción iterativa y delimitación del alcance.                                                |
| Presentación y primera entrega             | 7 de septiembre  | Preparación del informe, organización del repositorio, importación de la data a Python.                                                                               |
| Integración de datos y limpieza            | 14 de septiembre | Análisis de compatibilidad de las fuentes de información, tratamiento de valores faltantes y atípicos.                                                                |
| Enriquecimiento y feature engineering      | 21 de septiembre | Incorporación de las fuentes externas, ingeniería de atributos, definición de nuevas columnas.                                                                        |
| EDA                                        | 28 de septiembre | Análisis de escalas y distribuciones, normalización, análisis univariado y bivariado.                                                                                 |
| Análisis visual y segunda entrega          | 5 de octubre     | Preparación del informe, confección de visuales, narración de insights preliminares, comunicación de lo hallado.                                                      |
| Tests de hipótesis                         | 12 de octubre    | Análisis estadístico de las hipótesis planteadas, refutación o validación de hipótesis, confianza de los estimadores.                                                 |
| Fusión espacial y enriquecimiento complejo | 19 de octubre    | Integración de fuentes y variables geográficas, cálculo de distancias y densidades de servicios.                                                                      |
| Reducción de dimensionalidad               | 26 de octubre    | Empleo de PCA y MCA para hallar componentes de mayor impacto, creación de índices multivariados.                                                                      |
| Algoritmos predictivos y tercera entrega   | 2 de noviembre   | Análisis de similitud y clustering, y otros algoritmos predictivos a fin de entender pesos de variables.                                                              |
| Definición de la narrativa final           | 9 de noviembre   | Compilación de todos los hallazgos, desarrollo de tablero interactivo.                                                                                                |
| Presentación final                         | 16 de noviembre  | Exposición final, insights y recomendaciones principales, ponderación de fortalezas y debilidades, alcance y dificultades del análisis, y cierre del caso de negocio. |

# 2 Scraping y recolección 

El proceso de recolección de datos comenzó con el scraper proporcionado por la cátedra, adaptado y/o tomado de punto de partida para extraer registros de ArgenProp, ZonaProp, Airbnb, y Mercado Libre. En el caso de este último se hace uso de la API del sitio para acceder a la información.

En el caso particular de Airbnb, el scraper de la cátedra obtuvo 29 registros únicos tras recorrer 55 páginas. El motivo es que el sitio corta toda consulta en 15 páginas de 18 resultados (unos 270 anuncios) y a partir de ahí devuelve resultados repetidos. Al revisar esto se encontró además que Airbnb incluye el JSON completo de los resultados dentro del HTML de la página, por lo que no hace falta renderizarla con un navegador: alcanza con una petición simple. Sobre esa base se desarrolló un scraper propio.

Para superar el tope de resultados se dividió el territorio en celdas geográficas. Se consulta una celda; si alcanza el máximo de páginas, se la parte en cuatro y se repite el procedimiento sobre cada parte, hasta que cada celda entra completa. El criterio no es una estimación propia: el sitio informa cuántas páginas tiene realmente cada consulta. La ejecución final recorrió 147 celdas y obtuvo 11.276 anuncios, con mayor subdivisión en el corredor Palermo–Recoleta–Centro. La extracción se hizo en dos etapas: primero el censo de anuncios, y luego la ficha completa de cada uno, que aporta capacidad, calificaciones desagregadas, datos del anfitrión, reglas de la vivienda y el listado de comodidades. Entre pedidos se dejó un intervalo de 1,2 a 2 segundos, y no se registraron bloqueos.

Como Airbnb dejó de informar el barrio, éste se dedujo de las coordenadas contra el GeoJSON oficial de los 48 barrios, la misma fuente listada en el apartado 3.2. La asignación cubre el 99,2% de los registros.

Una particularidad de esta fuente es que el precio no es un atributo del inmueble, sino que depende de las fechas y de la cantidad de huéspedes consultadas. Por eso se relevaron dos series con ventanas fijas, ambas para dos huéspedes y con inicio el 20 de octubre de 2026: una de 5 noches y otra de 30. Los precios son comparables dentro de cada serie. Comparando entre ellas se observa un descuento mediano del 22,3% por estadía prolongada, y se identifican 1.500 anuncios que no aceptan estadías cortas, segmento cuya posible relación con el alquiler permanente será explorada mediante las hipótesis desarrolladas más adelante. Cabe aclarar que Airbnb no publica superficie en metros cuadrados, dirección exacta ni expensas. Se generan tres archivos por serie porque responden a usos distintos. El normalizado es el que entra al análisis comparativo entre portales: está filtrado a vivienda entera y usa el vocabulario común. El listings conserva todo sin decisiones tomadas de antemano, para poder revisar los criterios de filtrado. El amenities existe porque pasar 3.362 comodidades a columnas produciría un archivo de 3.400 columnas, en su mayoría con un único anuncio: el formato ancho conserva sólo las 168 presentes en al menos el 1% de los casos, y el largo preserva el resto.

En el caso de ArgenProp y ZonaProp, solo se consiguieron 162 y 980 registros, por encontrar bloqueos en la IP al pedir tanta información en poco tiempo. Aparte, como se usó `--listings-only`, hubo reducción en el detalle de la información. De esta manera, en el CSV creado hay muchos datos faltantes que podrían ser útiles para el análisis: datos de ubicación precisos, como latitud, longitud y barrio o datos propios de las viviendas, como si poseen balcón, terraza, ascensor, calefacción, entre muchos otros. El problema de la dirección se intentará resolver para un análisis futuro.

Cabe señalar que, si bien el alcance geográfico definido comprende la totalidad de CABA, la cobertura efectiva lograda no es homogénea entre fuentes. Mercado Libre y Airbnb aportan volúmenes sustanciales (44.013, 11.479 y 6.190 registros para venta, alquiler y alquiler temporal respectivamente en el primer caso, y 10.326 en el segundo), mientras que ArgenProp y ZonaProp quedaron acotados a 162 y 980 registros por los bloqueos de IP descriptos anteriormente. Esta asimetría implica que la representatividad barrio a barrio de estas dos últimas fuentes es limitada, y que ciertos barrios o segmentos del mercado podrían estar sub-representados en relación con su peso real en la oferta. Para mitigar este desequilibrio, el análisis territorial de mayor granularidad se apoyará principalmente en Mercado Libre y Airbnb, reservando ArgenProp y ZonaProp como fuentes complementarias y de contraste antes que como base primaria para comparaciones finas entre barrios. De ser posible, se evaluará ampliar la recolección de estas dos fuentes en etapas posteriores, espaciando las solicitudes para reducir el riesgo de bloqueo.

Para cada sitio, se ejecuta el scraper y se producen uno o más archivos csv con los registros de las publicaciones. Estas bases de datos son en este estado independientes; el proceso de scrapeo se realizó de manera aislada y adaptada a la estructura de cada portal, presentando los archivos finales distintos grados de compatibilidad. Si bien esto no presenta inconvenientes a la hora de analizar tendencias generales intrínsecas a cada base, se habilita en la etapa de limpieza de datos la posibilidad de trabajar sobre la unificación de formatos y fuentes, ponderando medidas de calidad, cantidad, compatibilidad, y usabilidad de datos.

# 3 Evaluación y planteo de hipótesis

## 3.1 Estado actual de la data recolectada

| **Archivo .csv**                | **Filas** | **Columnas** | **Fuente** | **Operación** | **Observaciones**                                                                         |
|---------------------------------|-----------|--------------|------------|---------------|-------------------------------------------------------------------------------------------|
| airbnb_caba_normalizado         | 10.326    | 59           | Airbnb     | Alq. temp     | Ventana de 5 noches. Vivienda entera, vocabulario homologado al de los demás portales.    |
| airbnb_caba_normalizado_mensual | 9.596     | 60           | Airbnb     | Alq. temp     | Ventana de 30 noches, misma fecha de inicio                                               |
| airbnb_caba_listings            | 11.276    | 287          | Airbnb     | Alq. temp     | Base completa: incluye habitaciones, alojamiento hotelero y columnas de comodidades seleccionadas |
| airbnb_caba_listings_mensual    | 10.369    | 288          | Airbnb     | Alq. temp     | Ídem, ventana mensual                                                                     |
| airbnb_caba_amenities           | 416.395   | 6            | Airbnb     | Alq. temp     | Formato largo: un registro por anuncio y comodidad                                        |
| airbnb_caba_amenities_mensual   | 466.706   | 6            | Airbnb     | Alq. temp     | Ídem, ventana mensual                                                                     |
| meli_alq_temp_x                 | 6190      | 61           | MeLi       | Alq. temp     | Compatibilidad de columnas con otros archivos de MeLi                                     |
| meli_alq_x                      | 11479     | 61           | MeLi       | Alquiler      | Compatibilidad de columnas con otros archivos de MeLi                                     |
| meli_vtas_x                     | 44013     | 61           | MeLi       | Vtas.         | Compatibilidad de columnas con otros archivos de MeLi                                     |
| propiedades_zonaprop            | 980       | 96           | ZonaProp   | Vtas. y Alqs. | Compatibilidad de columnas con ArgenProp. Mismo dataset para ventas y alquileres.         |
| propiedades_argenprop           | 162       | 96           | ArgenProp  | Vtas. y Alqs. | Compatibilidad de columnas con ZonaProp. Mismo dataset para ventas y alquileres.          |

En la próxima etapa se trabajarán cuestiones de cantidad, calidad, y compatibilidad de los datasets

## 3.2 Fuentes de enriquecimiento

A continuación se listan las potenciales fuentes de enriquecimiento de los datos, con variables demográficas, urbanísticas, económicas, o de otro modo útiles para el análisis.

|                                                                                                                                              | **Fuente** | **Observaciones**                                                      |
|----------------------------------------------------------------------------------------------------------------------------------------------|------------|------------------------------------------------------------------------|
| [<u>Listado de bibliotecas públicas</u>](https://data.buenosaires.gob.ar/dataset/bibliotecas)                                                | GCBA       | Bibliotecas públicas de la ciudad                                      |
| [<u>Listado de gastronómicos turísticos</u>](https://data.buenosaires.gob.ar/dataset/oferta-establecimientos-gastronomicos)                  | GCBA       | Establecimientos gastronómicos designados como de interés turístico    |
| [<u>Listado de establecimientos educativos</u>](https://data.buenosaires.gob.ar/dataset/establecimientos-educativos)                         | GCBA       | Escuelas y centros de educación públicos y privados                    |
| [<u>Listado de hospitales</u>](https://data.buenosaires.gob.ar/dataset/hospitales)                                                           | GCBA       | Centros de salud públicos y privados                                   |
| [<u>Listado de espacios culturales</u>](https://data.buenosaires.gob.ar/dataset/espacios-culturales)                                         | GCBA       | Espacios de cultura públicos y privados.                               |
| [<u>Listado de espacios verdes</u>](https://data.buenosaires.gob.ar/dataset/espacios-verdes)                                                 | GCBA       | Plazas, parques, y otros designados como espacio verde.                |
| [<u>Listado de estaciones de Subte</u>](https://data.buenosaires.gob.ar/dataset/subte-estaciones)                                            | GCBA       | Ubicación de las 90 estaciones                                         |
| [<u>Listado de uso de las estaciones de Subte</u>](https://data.buenosaires.gob.ar/organization/sbase)                                       | GCBA       | Uso detallado por estación y fecha. Página web con múltiples datasets. |
| [<u>Listado de corredores de MetroBus</u>](https://data.buenosaires.gob.ar/dataset/metrobus/resource/Juqdkmgo-1431222-resource)              | GCBA       | Corredores y estaciones del sistema de carriles para colectivos        |
| [<u>Listado de estaciones de ferrocarril</u>](https://data.buenosaires.gob.ar/dataset/estaciones-ferrocarril)                                | GCBA       | Estaciones de Trenes Argentinos.                                       |
| [<u>Censo poblacional 2022</u>](https://censo.gob.ar/index.php/datos_definitivos_caba/?utm_source=chatgpt.com)                               | INDEC      | Permite contar la cantidad de hogares por comuna.                      |
| [<u>USIG - Normalizador de Direcciones (API)</u>](https://servicios.usig.buenosaires.gob.ar/normalizar/)                                     | USIG       | Permite encontrar la latitud y longitud de una dirección.              |
| [<u>GeoJson de Barrios</u>](https://cdn.buenosaires.gob.ar/datosabiertos/datasets/innovacion-transformacion-digital/barrios/barrios.geojson) | GCBA       | Permite conocer el barrio correspondiente a una latitud y longitud.    |

Estas fuentes agregan información sobre el entorno urbano y permitirán la definición de columnas relativas a la presencia y/o densidad de estos servicios por geografía. También se incluyen indicadores sociales y económicos que forman parte del Censo poblacional de 2022, para enriquecer los perfiles geográficos hasta la granularidad disponible. Finalmente se incluyen fuentes para trabajar y compatibilizar ubicaciones geográficas en cuanto a coordenadas y direcciones.

En la etapa de ingeniería de atributos se evaluarán las operaciones necesarias para integrar los datasets y las variables potenciales que se podrán construir. Esto permitirá aportar indicadores de entorno urbano a través de variables calculadas, a nivel barrio/comuna. El análisis a nivel de cada publicación individual será posible en la etapa de trabajo de fusión espacial, donde se hará uso de las fuentes y capacidades de geolocalización.

# 4 Formulación final

En base a la información y formatos disponibles, se decide finalmente como objetivo de la investigación el desarrollo de un análisis particular y comparativo de las diferentes operaciones (venta, alquiler permanente, y temporal), en dimensiones geográficas, económicas, y demográficas. Quedan excluidos del análisis componentes relativos a la rentabilidad financiera del desarrollo, alquiler, compra-venta, refacción, mejora de inmuebles, o cualquier otra actividad inmobiliaria como inversión.

## 4.1 Métricas y KPIs preliminares

Se definen indicadores como puntapié inicial para el estudio tanto de mercados individuales como para comparaciones entre tipos de operaciones.

- **Precio por m² en el barrio b** = Promedio, para las publicaciones del barrio b, de (precio de la publicación i / superficie en m² de la publicación i). Se calculará para venta y alquiler permanente.[^1]

- **Precio por dormitorio en el barrio b** = Promedio, para las publicaciones del barrio b con al menos un dormitorio, de (precio de la publicación i / cantidad de dormitorios de la publicación i). Se utilizará principalmente para comparar alquileres temporales y permanentes, debido a la ausencia de información de superficie en Airbnb.[^2]

- **Medidas de tendencia central y dispersión del precio por m²** = Se calcularán medidas como mediana, promedio, percentiles y dispersión de los precios por m², diferenciando entre venta y alquiler permanente.

- **Participación de la operación i en el barrio b** = Publicaciones de la operación i en el barrio b / total de publicaciones en el barrio b.

- **Intensidad de oferta publicada en la comuna c** = Publicaciones de la operación i en la comuna c / población total de la comuna c × 1.000. Este indicador representa la cantidad de publicaciones por cada 1.000 habitantes y no debe interpretarse como cantidad de viviendas disponibles por habitante.[^3]

- **Densidad de servicios s en el barrio b** = Cantidad de establecimientos o puntos de servicio s en el barrio b / superficie del barrio b en km².

- **Prima asociada a un amenity a** = (Precio promedio de las publicaciones que mencionan el amenity a / Precio promedio de las publicaciones que no lo mencionan) − 1. El resultado se expresará como porcentaje y permitirá estimar la diferencia relativa de precio asociada a la presencia del atributo.[^4]

- **Brecha entre alquiler temporal y permanente en el barrio b** = (Precio promedio por dormitorio del alquiler temporal en el barrio b / Precio promedio por dormitorio del alquiler permanente en el barrio b) − 1. El resultado permitirá observar la diferencia relativa entre ambas modalidades.[^5]

- **Oferta de ambientes n en el barrio b** = Cantidad de publicaciones de n ambientes en el barrio b / total de publicaciones en el barrio b.

- **Brecha norte-sur del indicador i** = (Valor del indicador i en los barrios del norte − valor del indicador i en los barrios del sur) / valor del indicador i en los barrios del sur.

Estos indicadores y otros convenientes serán implementados en la etapa de ingeniería de atributos, de acuerdo con las necesidades de análisis y posibilidades técnicas de formato, calidad, etc.

## 4.2 Hipótesis a contrastar

Las hipótesis se formulan como relaciones contrastables entre variables observables. Se distinguirán las hipótesis centrales, directamente vinculadas con las decisiones públicas priorizadas, de los análisis complementarios. Debido al carácter observacional y transversal de los datos, su contrastación permitirá identificar asociaciones, pero no atribuir causalidad.

| | Formulación | Variable explicativa principal | Variable de resultado | Comparación y controles previstos |
|---|---|---|---|---|
| **H1 — Concentración turística** | Los barrios con mayor atractivo turístico y cultural presentan una mayor densidad de alojamientos temporarios completos. | Densidad de espacios culturales, gastronómicos, turísticos y verdes. | Alojamientos temporarios completos por 1.000 viviendas y participación del alquiler temporario en la oferta publicada. | Control por centralidad, población, stock habitacional, superficie del barrio y accesibilidad al transporte. |
| **H2a — Adecuación demográfica** | Los barrios o comunas con mayor proporción de hogares unipersonales presentan una mayor participación de monoambientes y unidades de uno o dos ambientes en la oferta publicada. | Proporción de hogares unipersonales. | Participación de unidades pequeñas dentro de la oferta residencial. | Separación por modalidad y fuente; control por centralidad, densidad poblacional y composición del stock habitacional cuando esté disponible. |
| **H2b — Servicios y concentración de oferta** | Las zonas con mayor disponibilidad de servicios urbanos presentan una mayor intensidad de oferta inmobiliaria publicada. | Densidad o proximidad de establecimientos educativos, sanitarios, culturales y espacios verdes. | Publicaciones por 1.000 habitantes, hogares o viviendas. | Análisis separado por tipo de servicio y modalidad; control por población, stock habitacional, superficie y centralidad. |
| **H3 — Transporte y precio** | Entre propiedades comparables, una menor distancia al transporte público masivo se asocia con un mayor precio publicado. | Distancia a estaciones de subte, tren y MetroBus, diferenciadas por medio. | Precio por m² para venta y alquiler permanente; precio por dormitorio para comparaciones que incluyan Airbnb. | Comparación dentro de zonas y tipologías semejantes; control por barrio, superficie, ambientes, tipo de propiedad, fuente y amenities disponibles. |
| **H4 — Presión potencial del alquiler temporario** | Los barrios con mayor densidad de alojamientos temporarios completos presentan una menor disponibilidad relativa de alquiler permanente y mayores precios residenciales publicados. | Alojamientos temporarios completos por 1.000 viviendas. | Alquileres permanentes publicados por 1.000 viviendas y nivel de precios residenciales. | Control por centralidad, atractivo turístico, población, stock habitacional, tipología y accesibilidad. No se interpretará la asociación como evidencia de desplazamiento o sustitución causal. |

### Criterios de contrastación

- Se definirá para cada hipótesis una unidad geográfica común —barrio o comuna— según la menor granularidad compatible entre las fuentes utilizadas.
- Los conteos de publicaciones se normalizarán por población, hogares, viviendas o superficie, evitando comparar valores absolutos entre zonas de distinto tamaño.
- Se exigirá un mínimo de observaciones por zona y modalidad antes de calcular indicadores o realizar comparaciones; el umbral se fijará durante el EDA.
- Las relaciones bivariadas se utilizarán como exploración inicial. Cuando sea posible, se aplicarán modelos multivariados o comparaciones estratificadas para controlar diferencias de centralidad, tipología y composición territorial.
- Se reportarán magnitud del efecto, incertidumbre y sensibilidad a distintas definiciones, además del p-valor cuando corresponda.
- Si la granularidad, cobertura o calidad de una fuente no permite contrastar una hipótesis, esta se reformulará o se informará como limitación, en lugar de forzar la integración.

# 5 Fuentes bibliográficas

\(1\) [<u>https://www.estadisticaciudad.gob.ar/eyc/wp-content/uploads/2026/08/Indicadores-26_08_26.pdf</u>](https://www.estadisticaciudad.gob.ar/eyc/wp-content/uploads/2026/08/Indicadores-26_08_26.pdf)

\(2\)
[<u>https://www.argentina.gob.ar/sites/default/files/ley_alquileres_informe_1410.pdf](https://www.argentina.gob.ar/sites/default/files/ley_alquileres_informe_1410.pdf)

\(3\)

[<u>https://www.infobae.com/economia/2024/04/19/deficit-habitacional-porteno-por-que-hay-mas-de-200000-viviendas-vacias-y-en-que-barrios-estan</u>](https://www.infobae.com/economia/2024/04/19/deficit-habitacional-porteno-por-que-hay-mas-de-200000-viviendas-vacias-y-en-que-barrios-estan/?utm_source=chatgpt.com)


[^1]: Debido a la falta de datos de superficie en Airbnb, el precio por m² no se calculará para alquiler temporal. La comparación mediante esta métrica se limitará a venta y alquiler permanente, siempre considerando que sus precios corresponden a modalidades y periodicidades diferentes.

[^2]: El precio por dormitorio se utilizará para comparar alquiler temporal y alquiler permanente debido a la falta de información de superficie en Airbnb. Para evitar divisiones por cero, se excluirán de esta métrica las publicaciones sin dormitorios, aunque podrán analizarse por separado como monoambientes.

[^3]: Este indicador utiliza publicaciones inmobiliarias como aproximación a la oferta publicada. Una publicación no necesariamente representa una vivienda única ni implica que la operación se concrete.

[^4]: La prima mide una asociación descriptiva entre la presencia del atributo y el precio publicado; no implica que el amenity sea la causa de la diferencia observada.

[^5]: Los precios de alquiler temporal y permanente deberán normalizarse a una escala temporal comparable antes de calcular esta brecha. En particular, deberá definirse previamente si el precio se expresará por noche, mes u otra unidad temporal.
