# Validación del cierre

Fecha: 10 de noviembre de 2026. Entorno local Windows, Python 3.12.7. Instalación editable verificada con `pip install -r requirements.txt`; versiones analíticas en `constraints.txt`. No se ensayó una descarga nueva de las fuentes: se usaron snapshots y cache versionados.

Se ejecutaron 01–16 en orden, sin errores, guardando outputs. `validacion_ejecucion.txt` conserva el resumen de la ejecución y `reports/validacion_cierre.json` registra celdas, versiones y cifras. La validación de nbformat confirma que todas las celdas de código tienen execution_count y no contienen outputs de error. Los cambios posteriores de Markdown no alteran cálculos.

Pasaron 13 tests, incluidos coherencia mart/avisos, normalización de moneda, conteos barriales, listas y brechas. La instalación se comprobó también desde notebooks y fuera del repositorio, sin PYTHONPATH. Se verificaron las medianas fila a fila; los conteos usan las mismas poblaciones que 07.

## Tarjetas sobre avisos territoriales válidos

| Operación | Variable | n válido | Mediana |
|---|---|---:|---:|
| venta | precio_m2_usd | 43130 | 2717.391304 |
| alquiler | precio_m2_usd | 10293 | 13.868646 |
| venta | precio_venta_usd | 43256 | 138000.000000 |
| alquiler | precio_mensual_usd | 10385 | 586.242835 |

Cada n cuenta precios no nulos del mismo campo. La superficie recortada del scatter no reduce el universo de las tarjetas. Ver `control_superficies_dashboard.csv` para sus conteos específicos. Estos controles no certifican las medidas del informe publicado.

## Resultado negativo de utilidad

| Referencia | MAE log(1+y), venta |
|---|---:|
| cluster_k2 | 0.240739 |
| cluster_k3 | 0.247174 |
| comuna | 0.173253 |
| global | 0.225176 |

Ambas soluciones de cluster tienen más error que la mediana global en venta. La comparación pareada y sus IC están en `valor_incremental_pareado_v2.csv`; no se cambia ese resultado por una comparación más favorable.

## Depuración y límites

Se retiraron 27 archivos enumerados (333305767 bytes previos): 22 copias completas sin consumidor y cinco salidas reemplazadas. Ninguno fue recreado al ejecutar la cadena final. Se conservaron los insumos entre etapas, la base enriquecida, la cache y los outputs finales. `data/raw/` no tiene cambios. No se reescribe el historial de Git.

Hay advertencias del entorno de Jupyter en Windows sobre el bucle de eventos y transporte del kernel; no se clasificaron como errores ni se confundieron con validación estadística. Las rutas de procedencia pueden reflejar separadores del sistema operativo y los metadatos de ejecución pueden variar; la comprobación de consistencia se hace sobre claves, poblaciones y cálculos, no sobre identidad byte a byte de todos los archivos.

CI: configurado para cada push a main, con instalación, tests, ejecución completa, depuración y control final. Usa el commit del evento y permisos de lectura; no escribe automáticamente en main. El resultado remoto debe consultarse en Actions para el SHA entregado; este registro documenta los controles locales y no anticipa un resultado remoto.

Pendiente del equipo: aplicar y comprobar los ajustes visuales de Power BI y preparar PPT con estas cifras. H3b, predicción de composición, amenities y norte–sur quedan justificadas como no estimadas, con consecuencias explícitas en README.
