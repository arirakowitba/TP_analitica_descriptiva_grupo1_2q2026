from pathlib import Path

README = Path("README.md")

if not README.exists():
    raise FileNotFoundError("No encuentro README.md. Ejecutar este script desde la raíz del repo.")

text = README.read_text(encoding="utf-8")

indice = """## Índice

- [0 Organización del repositorio](#0-organización-del-repositorio)
- [1 Caso de negocio](#1-caso-de-negocio)
- [2 Scraping y recolección](#2-scraping-y-recolección)
- [3 Evaluación y planteo de hipótesis](#3-evaluación-y-planteo-de-hipótesis)
- [4 Formulación final](#4-formulación-final)
- [5 Estado analítico actual](#5-estado-analítico-actual)
- [6 Fuentes bibliográficas](#6-fuentes-bibliográficas)

"""

estado_02 = """## 0.2 Estado actual de avance

- Repositorio organizado con datos crudos, scripts de extracción, notebooks por etapa, funciones reutilizables y salidas procesadas versionadas.
- Fuentes principales relevadas: Mercado Libre, Airbnb, ZonaProp y ArgenProp. La base consolidada actual contiene **67.887 publicaciones**: 43.345 de venta, 10.452 de alquiler permanente y 14.090 de alquiler temporario.
- Se completó el perfilado inicial, limpieza, normalización de categorías, tratamiento de duplicados, diagnóstico de nulos, imputaciones determinísticas, flags de faltantes, análisis de outliers, consolidación, EDA inicial, integración de fuentes externas, feature engineering territorial y un primer notebook de contraste de hipótesis.
- La base enriquecida final disponible en `data/processed/df_publicaciones_enriquecidas_v1.csv` tiene **67.887 filas y 90 columnas**, con precios comparables en USD, barrio/comuna oficial, distancias a transporte y servicios, indicadores censales y variables contextuales por barrio.
- Los reportes intermedios se guardan en `data/processed/reports`, para que las decisiones metodológicas no dependan solamente de la lectura visual de los notebooks.

"""

flujo_notebooks = """## 0.3 Flujo de notebooks

| Notebook | Propósito | Salidas principales |
|---|---|---|
| `01_perfilado_calidad_raw.ipynb` | Inventario de archivos, columnas, tipos, ejemplos, nulos, rangos y cardinalidad. | `inventario_raw.csv`, `perfil_calidad_raw.csv`, diccionario inicial. |
| `02_normalizacion_y_limpieza.ipynb` | Normalización de nombres, categorías, fechas, barrios, monedas, duplicados y consolidación inicial. | Datasets preprocesados por fuente y `df_publicaciones_consolidadas_v1.csv`. |
| `03_analisis_de_nulos_con_tests_hipotesis.ipynb` | Matrices de faltantes, nulos vs cuantitativas, nulos por labels, pruebas de asociación y decisiones de tratamiento. | Datasets con flags de nulos y reportes de decisiones. |
| `04_outliers.ipynb` | Detección de valores atípicos con IQR, percentiles, gráficos y análisis contextual. | Datasets con flags de outliers y reporte IQR. |
| `05_feature_engineering_y_eda_inicial.ipynb` | EDA previo a fuentes externas: composición, cobertura, precios, superficies, barrios y calidad remanente. | Reportes de EDA inicial. |
| `06_fuentes_externas.ipynb` | Carga, documentación e integración de fuentes externas; geocodificación y validación territorial. | Inventario de fuentes, ubicación de publicaciones, contexto urbano por barrio. |
| `07_feature_engineering.ipynb` | Normalización monetaria, precios comparables, distancias, conteos cercanos y KPIs por barrio/comuna. | `df_publicaciones_enriquecidas_v1.csv`, `kpis_barrio_v1.csv`, `kpis_comuna_v1.csv`. |
| `08_eda_con_fuentes_externas.ipynb` | EDA con fuentes externas, KPIs y primeras pruebas para contrastar las hipótesis del README. | Correlaciones, modelos, gráficos y síntesis de hipótesis. |

"""

estado_analitico = """# 5 Estado analítico actual

Esta sección resume lo que ya fue ejecutado en los notebooks y deja documentadas las principales decisiones tomadas. El objetivo es que el lector pueda entender el recorrido sin abrir todos los archivos, y que luego pueda auditar cada afirmación en `data/processed` y `data/processed/reports`.

## 5.1 Base consolidada y cobertura

La base consolidada contiene **67.887 publicaciones** de cuatro fuentes:

| Fuente | Publicaciones |
|---|---:|
| Mercado Libre | 57.149 |
| Airbnb | 9.596 |
| ZonaProp | 980 |
| ArgenProp | 162 |

Por operación, la base queda compuesta por **43.345 ventas**, **10.452 alquileres permanentes** y **14.090 alquileres temporarios**. La asimetría entre fuentes es importante: Mercado Libre y Airbnb sostienen la mayor parte del análisis, mientras que ZonaProp y ArgenProp se usan como contraste y complemento por su menor cobertura.

La cobertura territorial final es alta: `barrio_oficial` y `comuna_oficial` están completos en el **99,7%** de los registros enriquecidos. Las coordenadas están disponibles en el **86,9%** de las publicaciones. Esta diferencia se explica principalmente por ZonaProp, que conserva barrio/comuna pero no trae dirección suficiente para geocodificar con USIG.

## 5.2 Limpieza, normalización y duplicados

Se mantuvo una lógica conservadora: no se reemplazaron valores centrales cuando no había evidencia suficiente, y se priorizó reconstruir variables derivables antes que imputarlas estadísticamente.

Decisiones principales:

- Se normalizaron nombres de barrios, monedas, operaciones, fechas y columnas canónicas entre fuentes.
- `Las Cañitas` se trató como subzona de Palermo y se asignó a la comuna correspondiente.
- `localidad` se eliminó cuando solo indicaba CABA, porque no aporta variación dentro del alcance del trabajo.
- Se separaron ArgenProp y ZonaProp por tipo de operación antes de analizar nulos, ya que mezclar ventas y alquileres generaba faltantes estructurales difíciles de interpretar.
- Se completó `comuna` desde `barrio_norm` cuando había correspondencia oficial barrio-comuna. Esto imputó 164 comunas en MeLi alquiler, 148 en MeLi temporario, 544 en MeLi venta y 918 en ZonaProp; en ArgenProp no se imputó porque el campo de barrio no era confiable.
- No se eliminaron filas por faltantes críticos en esta etapa. Se crearon flags y se dejó la exclusión para KPIs específicos cuando falta la variable necesaria.

Duplicados:

- No se encontraron duplicados exactos en los raw.
- En Mercado Libre sí aparecieron duplicados por `item_id`: 1.602 en alquiler, 1.696 en alquiler temporario y 1.235 en venta. Se deduplicaron por identificador de publicación.
- En ArgenProp, ZonaProp y Airbnb no se detectaron duplicados por URL o `property_id`.
- Los duplicados inter-fuente no aparecieron con la regla aplicada. La ausencia de coincidencias se interpreta con cautela, porque las fuentes no comparten identificadores y algunas direcciones son incompletas.

## 5.3 Nulos y decisiones de tratamiento

El diagnóstico de nulos se hizo en dos momentos: primero sobre los datasets originales preprocesados, y luego después de ajustes derivados del propio análisis. Esto permite mostrar el camino de decisión: se observan los patrones, se corrigen problemas estructurales y recién después se decide qué tratar.

Criterios usados:

| Caso | Decisión |
|---|---|
| Columnas 100% vacías | Borrar, salvo que sean necesarias para mantener compatibilidad temporal del pipeline. |
| Columnas con muchos nulos y sin presencia útil en otros datasets | Borrar. |
| Columnas con muchos nulos pero reconstruibles desde texto, rangos o variables equivalentes | Mantener para reconstrucción. |
| Variables objetivo o críticas, como precio, moneda, barrio, superficie y ambientes | No imputar con medias/modas; reconstruir solo si hay evidencia. |
| Variables derivadas, como `precio_m2_ref` | Recalcular desde sus componentes válidos. |
| Variables categóricas con faltantes informativos, como inmobiliaria/seller | Mantener flag; usar `no_informado` solo para gráficos cuando corresponda. |

En expensas se decidió no reemplazar nulos por 0, porque "no informado" no significa "sin expensas". En cocheras, en cambio, se dejó una regla más operativa: puede imputarse 0 cuando el texto no identifica cochera, pero conservando la posibilidad de reconstrucción textual si la publicación la menciona.

## 5.4 Outliers

Los outliers se marcaron, pero no se eliminaron automáticamente. En real estate, los extremos pueden ser propiedades reales: unidades premium, superficies muy grandes, amenities de lujo, publicaciones temporarias con estadías particulares o errores de carga. Por eso se usaron flags antes que filtros destructivos.

El análisis detectó outliers por percentiles p01-p99 en todos los segmentos: 617 en MeLi alquiler, 268 en MeLi temporario, 2.635 en MeLi venta, 6 en ArgenProp venta, 14 en ArgenProp alquiler, 27 en ZonaProp venta, 33 en ZonaProp alquiler y 767 en Airbnb. Además, Airbnb mostró 1.650 valores inválidos en variables cuantitativas revisadas. Estos registros no se borraron; quedan identificados para decidir su uso según el KPI o análisis.

## 5.5 Fuentes externas e ingeniería de variables

El enriquecimiento territorial incorpora 12 fuentes o componentes:

| Componente | Uso principal |
|---|---|
| Censo 2022 por comuna | Denominadores de población, viviendas, hogares, hogares inquilinos y composición habitacional. |
| GeoJSON oficial de barrios | Asignación de barrio oficial, comuna y superficie. |
| USIG | Geocodificación de direcciones de portales sin coordenadas. |
| Dólar MEP diario | Normalización de precios ARS a USD según fecha de extracción. |
| Subte, tren y MetroBus | Distancias a transporte masivo y densidades por barrio. |
| Espacios verdes | Distancia y porcentaje de superficie verde por barrio. |
| Educación, hospitales, cultura y gastronomía turística | Conteos, densidades y servicios cercanos. |

Variables derivadas relevantes:

- `precio_venta_usd`, `precio_mensual_usd`, `precio_m2_usd` y `precio_por_ambiente_usd`.
- `barrio_oficial`, `comuna_oficial`, `lat`, `lon`, `metodo_geo` y `origen_barrio`.
- `dist_subte_m`, `dist_tren_m`, `dist_metrobus_m`, `dist_transporte_masivo_m` y `dist_espacio_verde_m`.
- `n_culturales_500m`, `n_gastronomia_500m` y `n_educacion_500m`.
- Densidades por km² de transporte, educación, hospitales, cultura, gastronomía y espacios verdes.
- KPIs por barrio y comuna: publicaciones por 1.000 habitantes/viviendas, Airbnb por km², brechas temporario-permanente y medianas de precio.

La cobertura de variables enriquecidas es desigual: precios por ambiente están disponibles en el **98,6%** de los registros, precio por m² en el **79,1%**, y distancias/servicios cercanos en el **86,9%**, atados a la disponibilidad de coordenadas.

## 5.6 Hallazgos preliminares del EDA

Estos resultados son descriptivos y sirven para orientar el análisis posterior, no para afirmar causalidad.

- La oferta de venta domina el volumen total: 43.345 publicaciones frente a 10.452 alquileres permanentes y 14.090 temporarios.
- El alquiler temporario está mucho más concentrado territorialmente. Palermo reúne 3.222 anuncios de Airbnb, Recoleta 1.322 y San Nicolás 568.
- En términos de densidad, San Nicolás, Recoleta, Palermo y Monserrat aparecen entre los barrios con mayor presión temporaria por km².
- La comuna 14 concentra 3.222 Airbnb y tiene 21,37 Airbnb cada 1.000 viviendas, frente a 9,49 alquileres permanentes cada 1.000 viviendas.
- En precios publicados, las ventas se expresan casi siempre en USD, mientras que los alquileres combinan ARS y USD. Por eso la normalización monetaria con MEP es necesaria antes de comparar.
- El precio por m² y el precio por ambiente se usan de forma complementaria: Airbnb no tiene superficie, y Mercado Libre casi no informa dormitorios de manera comparable.

## 5.7 Primera contrastación de hipótesis

El notebook 08 evalúa las hipótesis formuladas en este README con variables observables. En algunos casos se usan proxies porque la fuente ideal no está disponible al nivel geográfico necesario.

| Hipótesis | Evidencia actual | Lectura preliminar | Limitación principal |
|---|---|---|---|
| H1 - Concentración turística | Cultura por km² se asocia fuertemente con Airbnb relativo: rho = 0,85 por barrio y 0,86 por comuna. Gastronomía también acompaña: rho = 0,65 por barrio. | Evidencia a favor. | Puede estar confundida con centralidad urbana. |
| H2a - Adecuación demográfica | La relación entre tamaño medio del hogar y unidades chicas queda entre rho = -0,50 y 0,01 según operación. | Sin evidencia clara. | El Censo disponible no trae hogares unipersonales por comuna; se usa tamaño medio como proxy débil. |
| H2b - Servicios y oferta | En alquiler por 1.000 viviendas, cultura rho = 0,69, gastronomía rho = 0,66 y subte rho = 0,54. Escuelas, hospitales y verdes no muestran relación clara. | Evidencia parcial. | Los servicios asociados parecen capturar centralidad más que servicios barriales en general. |
| H3 - Transporte y precio | En modelos con controles, el efecto por 100 m más lejos del transporte masivo es pequeño y de signo contrario a lo esperado: venta +0,8% y alquiler +1,0%. | Sin apoyo para la hipótesis original. | Distancia en línea recta, geocodificación parcial y posible confusión con avenidas o corredores caros. |
| H4 - Presión temporaria | Airbnb se asocia positivamente con precio de alquiler (rho = 0,91) y también con alquileres permanentes por 1.000 viviendas (rho = 0,83). | No evaluable como desplazamiento. | Con corte transversal y 15 comunas no se puede separar presión temporaria de centralidad/coubicación. |

## 5.8 Lectura metodológica y próximos pasos

El proyecto ya cuenta con una base sólida para avanzar hacia la entrega final: el pipeline distingue datos observados, variables reconstruidas, variables derivadas, flags de calidad y fuentes externas. Esto reduce el riesgo de construir KPIs sobre transformaciones opacas.

Próximos pasos:

/- Refinar las visualizaciones y narrativa del notebook 08, separando evidencia, interpretación y limitaciones.
/- Incorporar controles de centralidad en H1, H2b y H4, por ejemplo con distancia al microcentro o efectos territoriales.
/- Explorar segmentación de barrios/comunas a partir de KPIs inmobiliarios, censales y de entorno urbano.
/- Definir variables modelables y variables solo descriptivas, especialmente aquellas afectadas por imputaciones o reconstrucción.
/- Preparar un pipeline más determinístico para las transformaciones ya validadas durante la exploración.

"""

estado_analitico = estado_analitico.replace("\n+/- ", "\n- ")


def replace_between(src: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = src.find(start_marker)
    if start == -1:
        raise ValueError(f"No encuentro el marcador inicial: {start_marker!r}")
    end = src.find(end_marker, start + len(start_marker))
    if end == -1:
        raise ValueError(f"No encuentro el marcador final: {end_marker!r}")
    return src[:start] + replacement + src[end:]


if "## Índice" not in text:
    marker = "2Q 2026\n\n"
    if marker not in text:
        raise ValueError("No encuentro el lugar para insertar el índice.")
    text = text.replace(marker, marker + indice, 1)

text = replace_between(text, "## 0.2 Estado actual de avance", "# 1 Caso de negocio", estado_02 + flujo_notebooks)

text = text.replace(
    "En la próxima etapa se trabajarán cuestiones de cantidad, calidad, y compatibilidad de los datasets",
    "Luego del perfilado inicial, estas bases fueron normalizadas y consolidadas en notebooks separados. El análisis de calidad mostró que los faltantes no son homogéneos: una parte corresponde a ausencias reales de cada publicación y otra a diferencias estructurales entre portales. Por eso el tratamiento se realizó por fuente y por operación antes de consolidar.",
)

text = text.replace(
    "| [<u>Listado de bibliotecas públicas</u>](https://data.buenosaires.gob.ar/dataset/bibliotecas)                                                | GCBA       | Bibliotecas públicas de la ciudad                                      |\n",
    "",
)
text = text.replace(
    "| [<u>Listado de uso de las estaciones de Subte</u>](https://data.buenosaires.gob.ar/organization/sbase)                                       | GCBA       | Uso detallado por estación y fecha. Página web con múltiples datasets. |\n",
    "",
)
text = text.replace(
    "Estas fuentes agregan información sobre el entorno urbano y permitirán la definición de columnas relativas a la presencia y/o densidad de estos servicios por geografía. También se incluyen indicadores sociales y económicos que forman parte del Censo poblacional de 2022, para enriquecer los perfiles geográficos hasta la granularidad disponible. Finalmente se incluyen fuentes para trabajar y compatibilizar ubicaciones geográficas en cuanto a coordenadas y direcciones.\n\nEn la etapa de ingeniería de atributos se evaluarán las operaciones necesarias para integrar los datasets y las variables potenciales que se podrán construir. Esto permitirá aportar indicadores de entorno urbano a través de variables calculadas, a nivel barrio/comuna. El análisis a nivel de cada publicación individual será posible en la etapa de trabajo de fusión espacial, donde se hará uso de las fuentes y capacidades de geolocalización.",
    "Estas fuentes agregan información sobre el entorno urbano y permiten definir columnas relativas a presencia, proximidad y densidad de servicios por geografía. También se incluyen indicadores sociales y habitacionales del Censo 2022, para enriquecer los perfiles geográficos hasta la granularidad disponible. Finalmente se incluyen fuentes para compatibilizar ubicaciones mediante coordenadas, direcciones y polígonos oficiales.\n\nDurante la integración se descartaron bibliotecas y pasajeros de subte como fuentes centrales. Las bibliotecas quedan parcialmente contenidas dentro de espacios culturales y el uso de subte no se incorpora por estación comparable, porque la fuente disponible se presenta por línea/año y no por punto territorial directamente asociable a cada publicación. Esta decisión evita sumar variables atractivas en apariencia pero débiles para las hipótesis del trabajo.",
)

if "# 5 Estado analítico actual" in text:
    text = replace_between(text, "# 5 Estado analítico actual", "# 6 Fuentes bibliográficas", estado_analitico)
elif "# 5 Fuentes bibliográficas" in text:
    text = text.replace("# 5 Fuentes bibliográficas", estado_analitico + "# 6 Fuentes bibliográficas", 1)
else:
    raise ValueError("No encuentro la sección de fuentes bibliográficas para insertar el estado analítico.")

README.write_text(text, encoding="utf-8")
print("README.md actualizado.")
