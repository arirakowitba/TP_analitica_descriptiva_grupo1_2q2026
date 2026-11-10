# Análisis inmobiliario y habitacional de CABA

Ariel Rakowsczyk · Gaetano Murchio · Juan Cruz Moyano · Miranda Contieri Quiles

Analítica Descriptiva · 2Q 2026

## Problema y decisiones

El Instituto de Vivienda necesita localizar zonas donde profundizar el diagnóstico de la oferta publicada. El proyecto integra portales inmobiliarios, contexto urbano y Censo 2022. La unidad es el aviso por fuente y operación; no una vivienda única, un contrato ni una transacción. El corte de 2026 no identifica desplazamiento residencial ni evolución del stock.

Las decisiones se mantienen separadas:

1. **Monitorear el temporario:** ordenar comunas por Airbnb por 1.000 viviendas; conservar precio de alquiler, ratio Airbnb/permanente y brechas mensuales por barrio como contexto. No exigir baja oferta permanente: H4 muestra co-ubicación, no sustitución.
2. **Diagnosticar oferta permanente:** ordenar de menor a mayor alquiler publicado por 1.000 hogares inquilinos. Verificar cobertura del portal y datos administrativos antes de interpretar escasez.
3. **Diagnosticar precios:** ordenar por mediana de USD/m²/mes del alquiler permanente, con al menos 30 precios válidos. No equivale a asequibilidad: faltan ingresos y condiciones contractuales.

La accesibilidad y las tipologías contextualizan esas listas. No hay evidencia para asignar obras, subsidios o fiscalizaciones automáticamente. Los perfiles multivariados describen el entorno y no agregan una cuarta prioridad.

## Resultados y límites

| Hipótesis | Qué se calcula | Lectura final | Evidencia |
|---|---|---|---|
| H1 · atractivo urbano | Spearman de cultura/gastronomía con **avisos Airbnb / avisos de alquiler permanente**, por barrio | Asociación positiva; persiste con controles aproximados de centralidad. Dependencia espacial y selección impiden lectura causal. Airbnb/km² es solo una descripción cartográfica distinta. | 08 y 16; `reports/robustez_pe3/hipotesis_primarias_v2.csv` y `rangos_parciales_centralidad_v2.csv` |
| H2a · hogares y tipologías | Tamaño medio de hogar frente a participación de departamentos de 1–2 ambientes, por comuna | Evidencia insuficiente. El proxy no mide hogares unipersonales; cambian cobertura y soporte según definición. | 08 y 16; `h2a_definicion_soporte_v2.csv` |
| H2b · servicios y oferta | Densidades de servicios frente a alquiler por 1.000 viviendas | Apoyo parcial para cultura, no generalizable a todos los servicios. | 16; familia territorial primaria y controles |
| H3 · transporte y precio | Modelos separados de venta y alquiler; superficie, ambientes, barrio y fuente; incertidumbre agrupada por barrio | Signo contrario al esperado. Venta es frágil a sensibilidades; alquiler conserva asociación pequeña positiva. RESET rechaza las formas evaluadas. No es una prima causal de transporte. | 12 y 16; `h3_sensibilidad_v2.csv`, `h3_especificacion_v2.csv`, `h3_formas_funcionales_v2.csv` |
| H4 · temporario y permanente | Airbnb/1.000 viviendas frente a precio de alquiler y alquileres/1.000 viviendas | Asociación con precios altos **y con mayor oferta permanente publicada**. La dirección de disponibilidad esperada no recibe apoyo. No demuestra sustitución. | 08 y 16; `matriz_evidencia_v2.csv` |

En H4, la asociación con disponibilidad permanente es positiva: `rho=+0,832`, n=15 comunas, IC95% `[0,507; 0,971]` (tabla `hipotesis_primarias_v2.csv`). Por eso se retira la combinación que exigía Airbnb alto y permanente bajo.

La familia territorial usa IC bootstrap, permutaciones bilaterales, BH/Holm, controles y leave-one-out; no constituye preregistro. Los IC son puntuales y condicionados al corte de portales. Las comunas, los barrios y los avisos no son unidades intercambiables.

**Utilidad de clusters.** En precio de venta, k=2 y k=3 son peores que la mediana global en MAE de log(1+y), y comuna supera a los tres. Este resultado negativo impide recomendar clusters como reemplazo de comuna. La validación LOO reajusta escala, PCA y clustering sin el barrio evaluado; no usa precio para construir grupos. Comparar únicamente con comuna ocultaría que ni siquiera mejoran la referencia global. Ver `comparacion_clusters_comunas_v2.csv` y los IC de diferencias pareadas en `valor_incremental_pareado_v2.csv`.

PCA, MCA, análisis factorial y densidad cultural describen principalmente un gradiente de centralidad. Se conserva PCA como representación del entorno y comuna como referencia operativa. Los notebooks 13–14 quedan como diagnósticos complementarios de composición y adecuación, sin sumar evidencia independiente ni alimentar otra lista de intervención.

## Listas operativas y revisión

El notebook 09 genera [listas completas](data/processed/reports/listas_operativas_comunas.csv), [sensibilidad](data/processed/reports/sensibilidad_listas_operativas.csv) y [brechas mensuales](data/processed/reports/brechas_monitoreo.csv). Cada fila conserva indicador, puesto, conteos por operación, número de precios, IC de la mediana, mezcla de monedas, rango de puestos y fracción de escenarios seleccionada.

Los escenarios cruzan cortes P60/P70/P75/P80/P90, mínimos de 20/30/50/100 precios para la lista de precios y MEP −10%, base, +10% aplicado solo a ARS. Se mantiene fijo el conjunto de precios válidos de base: el shock modifica conversión, no reclasifica los flags. No son probabilidades de necesidad. No se exige precio disponible para ordenar una lista de conteos. En conteos no se inventa un IC poblacional: la incertidumbre principal es cobertura y captura.

La [revisión de primeros puestos](docs/revision_listas_operativas.md) documenta composición, soporte, sensibilidad y siguiente acción. Las brechas temporal/permanente usan medianas mensuales por ambiente y fuentes separadas; no comparan rentabilidad de contratos equivalentes.

## Preguntas cerradas por alcance

| Pregunta | Estado y justificación | Consecuencia |
|---|---|---|
| H3b: magnitud similar de transporte/precio entre tres operaciones | **No contrastada; retirada de las conclusiones.** La formulación histórica está en README de `b70aaae`. Venta y alquiler tienen escalas distintas y Airbnb no aporta superficie comparable; 30 noches y contrato permanente son productos diferentes. Comparar dos coeficientes o p-valores no prueba igualdad. Haría falta métrica común defendible, soporte comparable e interacción o prueba de equivalencia con margen sustantivo. | No afirmar que el efecto de transporte sea igual entre operaciones. La variable local `perfil_distancia` de 08 es un perfil descriptivo de venta/alquiler, no la prueba de aquella hipótesis. |
| Predicción de distribución de operaciones por zona | **No implementada; fuera del alcance final.** La composición observada se reporta en 08, pero no hay validación geográfica/temporal de un predictor de participaciones y el portal está confundido con operación. Clustering, AMI y R² de precios no responden esta pregunta. | No pronosticar futuras participaciones ni demanda. Requiere snapshots y validación que preserve grupos territoriales/fuente. |
| Prima por amenities | **No estimada.** El dataset enriquecido no conserva una medición armonizada de presencia/ausencia. No mencionar un atributo no equivale a ausencia, y los vocabularios difieren por portal. Los amenities de Airbnb existen en raw pero no justifican una prima transversal entre operaciones. | Se retira el KPI prometido; no extraer una prima del título ni presentar diferencia bruta como efecto de equipamiento. |
| Brecha norte–sur | **No estimada; retirada como KPI.** No se fijó una partición norte/sur externa, población de referencia ni indicador único. El contraste comunas 1–3/resto de 16 es centralidad administrativa y no una brecha norte–sur. | No renombrar aquel contraste. Se conserva la desagregación por barrio/comuna sin inventar una división después de observar resultados. |

Estas restricciones no afectan las listas descriptivas, pero limitan su uso para prescribir intervenciones, estimar demanda o explicar causalmente precios.

## Dashboard y presentación

[Informe público de Power BI](https://app.powerbi.com/view?r=eyJrIjoiOGQ5ODllNTItODU4MS00OTEyLWFhMWItNjQwMGRhMjExYWE4IiwidCI6ImExZjUwYTk3LTIxYzAtNDlhNy1hOWQ0LWYyNDRlYmI0MmRhNyIsImMiOjR9&pageName=e377f501cce641b0905d). **Actualización visual pendiente del equipo responsable.** Este cierre no modifica ni verifica las medidas del informe publicado ni la presentación PPT.

El mart exporta `precio_venta_usd` y `precio_mensual_usd`, valores originales, moneda, MEP/fecha, flags y columnas aptas para tarjetas. Las medidas DAX calculan **medianas sobre avisos**, nunca promedios de medianas barriales. Cada tarjeta debe mostrar su n. La regla es USD original o ARS/MEP por fecha; Airbnb usa cotización de 30 noches. Moneda desconocida no se convierte. No se mezclan venta y mensualidad.

Las columnas de tarjetas aplican `en_alcance_territorial`, igual que los KPIs; los avisos excluidos permanecen en el hecho para auditoría. El filtro de plausibilidad respeta los rangos de `src/features.py`. El scatter agrega una restricción visual de superficie entre 10 y 2.000 m², documentada como recorte de visualización; no borra datos. Mantener filtro de operación y precio válido, unidad m² sin abreviatura automática y precio en su unidad correspondiente.

[Instrucciones y comprobaciones para Power BI](docs/ajustes_dashboard.md). [Valores y n esperados de tarjetas](data/processed/reports/control_tarjetas_dashboard.csv). Paquete: [dashboard_mart_powerbi.zip](data/processed/dashboard_mart_powerbi.zip). La publicación solo podrá darse por consistente cuando el equipo aplique medidas y compare los mismos filtros.

## Seguimiento verificable

| Observación | Estado | Qué cambió | Dónde verificar |
|---|---|---|---|
| Prioridad conjuntiva incompatible con H4 | Resuelta en código | Tres listas ordenadas por decisión, soporte, incertidumbre y sensibilidad | 09, 16; `src/priorizacion.py`; CSV de listas; revisión de primeros puestos |
| Tarjetas y moneda | Parcial | Precios normalizados, columnas válidas, DAX y control contra avisos; falta actualización visual | `src/build_dashboard_mart.py`; `src/validar_cierre.py`; `control_tarjetas_dashboard.csv` |
| H1 mal rotulada | Parcial | README y notebooks explicitan ratio Airbnb/permanente; falta rótulo del tablero | 08, 16 y `docs/ajustes_dashboard.md` |
| Borradores e interpretaciones automáticas | Resuelta en fuentes | Conclusiones escritas en Markdown junto a resultados; código conserva tablas/figuras | Notebooks 08–16 |
| Clusters vs mediana global en venta | Resuelta | Resultado negativo explícito y comparación de referencias | 16; `comparacion_clusters_comunas_v2.csv` |
| H3b, predicción, amenities y norte–sur | Resuelta por justificación; no estimadas | Alcance, requisitos faltantes y consecuencias declarados; sin afirmar resultados inexistentes | Tabla anterior y 08, 13, 16 |
| Brecha temporal/permanente | Resuelta | Se conecta a monitoreo, con fuentes, soporte e IC separados | 07, 09; `brechas_monitoreo.csv` |
| Nombres, ejes, tooltips y scatter del tablero | Pendiente del equipo | Instrucciones precisas y criterios de aceptación | `docs/ajustes_dashboard.md` |
| Depuración de datos | Resuelta | Se retiran copias sin consumidores y sus exportaciones; se preservan dependencias | `docs/depuracion_datos.md`; cadena 01–16 |
| Un solo proyecto | Resuelta en documentación | Narrativa por problema, evidencia y decisión; sin agenda de entregas | README y guías de carpetas |
| Reproducibilidad y CI | Resuelta local; CI en Actions | Tests de mart y priorización; CI en cada push, sin escritura automática a main | `.github/workflows/execute-notebooks.yml`; `docs/validacion_cierre.md` |

## Reproducir

Desde la raíz, con Python 3.12:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.run_notebooks_sequential
python -m src.validar_cierre
python -m unittest discover -s tests -v
```

`constraints.txt` fija las versiones analíticas verificadas; no es un lock completo de todas las dependencias transitivas.

El ejecutor utiliza el mismo intérprete para kernels y herramientas, guarda outputs y se detiene ante el primer error. Para reproducir desde crudos, conservar `data/raw/` y `data/processed/geocodificacion_usig_cache.csv`; los notebooks generan los demás insumos en orden. La cache evita llamadas a USIG y las fuentes externas se leen de snapshots locales. No se necesita repetir scraping. Los intermedios usados entre etapas se conservan; no se sustituyen por una base de un paso anterior si falta una dependencia.

| Etapa | Notebooks | Salida / función |
|---|---|---|
| Calidad, limpieza, nulos y outliers | 01–04 | Bases por fuente post-ajustes y consolidado con flags |
| Descripción, fuentes y variables | 05–08 | Base enriquecida, KPIs barriales/comunales, precios normalizados |
| Decisiones y perfiles | 09–11 | Listas, PCA y clusters descriptivos |
| Modelos y diagnósticos complementarios | 12–14 | Modelos explicativos; composición y adecuación de representaciones |
| Integración y validación | 15–16 | Mart Power BI, auditoría de hipótesis y robustez |

`data/raw/` preserva snapshots. `data/processed/` conserva dependencias y resultados finales. `src/` contiene lógica reutilizable; `tests/`, contratos; `docs/`, metodología y pendientes. Los identificadores técnicos de archivos existentes se conservan para no romper dependencias.

Fuentes y extracción: [scrapers](docs/scrapers.md), [Airbnb](docs/scraper_airbnb.md). Modelo del dashboard: [guía dimensional](docs/modelo_data_warehouse_dashboard.md). Los límites principales son selección por portal, posibles duplicados entre portales, geocodificación, superficie no comparable en Airbnb, desfase Censo 2022/corte 2026 y ausencia de series de contratos/stock.
