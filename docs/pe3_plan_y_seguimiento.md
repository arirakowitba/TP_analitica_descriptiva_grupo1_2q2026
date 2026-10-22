# Seguimiento de PE3

**Estado al 22 de octubre de 2026.** Primer esqueleto de la tercera pre-entrega agregado a `main`, basado en la devolución PE2 (nota 8,8), la consigna PE3 y la secuencia actual 01–08.

## Acuerdos que guían los cambios

- Mantener intacta la limpieza y el feature engineering de 01–07 salvo que aparezca un error concreto.
- Priorizar aclaraciones de interpretación, README y nuevas celdas analíticas de bajo impacto.
- No mezclar unidades, fuentes ni modalidades de operación sin justificarlo.
- Mantener la distinción entre oferta publicada, stock censal, asociaciones y recomendaciones.
- Dashboard queda fuera de la secuencia de notebooks analíticos.
- Ejecutar todos los notebooks completos, en orden, y conservar outputs visibles para la entrega revisada.

## Notebooks incorporados

| Notebook | Contenido inicial | Salida principal |
|---|---|---|
| 09 | Cierre del EDA, síntesis de hipótesis, catálogo y jerarquía de KPIs, señales comunales exploratorias | síntesis PE3 y señales de diagnóstico en reports |
| 10 | PCA en KPIs barriales y MCA sobre niveles categorizados | cargas, varianza y coordenadas en processed/reports |
| 11 | K-means y Ward, silueta, estabilidad por submuestras y perfilado | asignación exploratoria de barrios y perfiles |
| 12 | Modelos log-lineales separados para venta/alquiler, comparación con y sin efecto fijo de fuente, errores agrupados por barrio | tabla de coeficientes e intervalos |

09 exporta el perfil de servicios y transporte que consume 10. 10 exporta las coordenadas que consume 11. 12 incorpora las etiquetas de 11 en una especificación explicativa separada, sin incluirlas en un modelo con efectos fijos por barrio. El PCA y el clustering no usan precios, para evitar circularidad en la lectura posterior. El notebook 08 recibió una aclaración textual para definir el tamaño medio del hogar como proxy indirecto, no como medida de hogares unipersonales. Los README ahora explicitan la limitación de precios nominales en USD/ARS y la falta de snapshots para estudiar inflación, dolarización y tipo de cambio.

## Decisiones provisionales que debemos revisar notebook por notebook

1. En 09, revisar si los cortes P75/P25 y la combinación de tres señales son útiles para priorizar diagnóstico adicional; no son umbrales normativos.
2. En 10, validar transformaciones logarítmicas, cobertura mínima de 75%, interpretación de las cargas y pertinencia de MCA con 48 barrios.
3. En 11, elegir el número de grupos mirando en conjunto silueta, ARI de estabilidad e interpretabilidad; no aceptar automáticamente el máximo de silueta.
4. En 12, revisar cobertura y comparabilidad de fuentes y verificar que la muestra y las variables replican el universo de H3.
5. Ajustar interpretación de resultados únicamente después de ejecutar los notebooks con los datos definitivos.
6. Revisar comparaciones múltiples y magnitud de efecto en H1/H2b; mantener el poder bajo de n=15 comunas y la naturaleza proxy de H2a.
7. El análisis transversal no demuestra que alquiler temporario desplace alquiler permanente; H4 se desagrega entre precios, intensidad publicada y disponibilidad.
8. Sigue pendiente re-ejecutar 08 con imágenes embebidas: en el estado remoto revisado había salidas de texto/tablas, pero ninguna salida de imagen PNG.
9. La validación final requerirá ejecución secuencial desde 01, outputs visibles, títulos autosuficientes, n e incertidumbre cuando correspondan.

## Estado de reproducción

Los nuevos notebooks son un primer abordaje de estructura y código. No se guardaron como notebooks ejecutados: deberán correrse secuencialmente en el entorno del repositorio para materializar outputs y revisar los resultados reales. Las salidas previstas son derivadas y se guardan en `data/processed/` o `data/processed/reports/`; no editan `data/raw/`.
