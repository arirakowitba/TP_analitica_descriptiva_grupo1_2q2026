# Protocolo de reconciliación y robustez PE3

Esta revisión agrega evidencia y borradores de interpretación. La definición final
de interpretaciones, la narrativa ejecutiva y la escritura del README se reservan
para el cierre con el equipo. No modifica limpieza, fuentes crudas ni enriquecimiento
de 01–07. Tampoco construye el dashboard visual: conserva el mart de 15.

## Cambios por notebook

| Notebook | Reconciliación o validación |
|---|---|
| 08 | Elimina cifras narrativas desactualizadas; síntesis calculada desde tablas y lectura provisional por hipótesis. |
| 09 | Lectura calculada del soporte y de las tres señales; remisión a sensibilidad de cortes. |
| 10 | Interpreta las variables realmente activas, varianza, pesos y calidad del plano; normaliza coordenadas principales MCA por masa de fila. |
| 11 | Perfiles con tamaños/KPIs reales; no emite inferencia asintótica si hay grupos con menos de cinco barrios; distingue descripción postselección y validación externa. |
| 12 | Efectos e IC calculados desde cada especificación; elimina atribuciones no medidas a ruido, tranquilidad o preferencias y afirmaciones de ausencia de sesgo. |
| 13 | Explicita soporte de la permutación fuente×barrio, AMI observado y media nula; gráfico de la distribución nula condicionada. |
| 14 | Revisa esperados del chi-cuadrado, conserva no estimables, reporta comunalidades y adecuación con interpretación provisional. |
| 15 | Repara saltos de línea literales y mantiene explícito que paquete de datos no equivale a PBIX terminado. |
| 16 | Auditoría transversal de hipótesis, centralidad, espacio, sensibilidad, PCA/factor, clusters y modelos. |

## Familias y preguntas

1. **Diez contrastes territoriales primarios:** H1 cultura/gastronomía y Airbnb relativo;
   H2a tamaño medio de hogar y tipología por tres operaciones; H2b cultura/educación/
   espacios verdes y oferta permanente; H4 precio y disponibilidad por separado.
   Spearman, IC bootstrap pareado (999), permutación bilateral (1.999), BH y Holm,
   dirección esperada y rango leave-one-out. La hipótesis estadística bilateral no
   reemplaza la dirección sustantiva formulada.
2. **Diez contrastes parciales de rangos:** mismos pares controlando centralidad y
   área; BH independiente, permutación aproximada de residuos con nueva proyección.
   Se reconoce intercambiabilidad y posible dependencia espacial.
3. **Diagnóstico espacial:** Moran I con vecinos 3 y 5 de centroides, más residuo
   de H1 controlada; aleatorización bilateral y BH de esta familia.
4. **Geografía definida externamente:** comunas 1–3 frente al resto. Mann–Whitney,
   KS, Brown–Forsythe, Cliff e IC de diferencia de medianas. Una observación por
   barrio; familias separadas según la pregunta (orden, distribución, dispersión).
5. **Sensibilidad sin selección por p:** definición H2a (uno/dos ambientes y soporte),
   cortes de priorización P60–P90, mínimos de avisos y conversión MEP ±10% solo
   sobre avisos ARS. Las fracciones de escenarios no son probabilidades de déficit.
6. **PCA/factor:** bootstrap de barrios con escalado reajustado, alineación de signo
   y componentes, intervalos de pesos y ángulos de subespacios. El bootstrap
   unifactorial se condiciona a adecuación y parallel analysis compatible.
7. **Clusters:** k=2 y k=3; exclusión de Puerto Madero, cambio de escala/log,
   dos/todos los componentes y referencia con inicialización idéntica,
   comparación con Ward. LOO territorial reajusta PCA, escala y clusters sin el
   barrio objetivo. KPIs suplementarios se predicen por mediana de entrenamiento;
   se compara contra comuna y mediana global con soporte/fallback explícitos.
   Diferencias pareadas de MAE log con bootstrap y Wilcoxon, BH conjunto.
8. **Precios:** venta y alquiler separados; errores agrupados por barrio con
   corrección finita y referencia t de G−1 grados. Diagnóstico de residuos,
   Q–Q, BP/JB orientativos, influencia Cook/leverage, RESET agrupado, curvatura
   y controles de fuente. BH para contrastes de especificación; dos contrastes
   primarios H3 en su propia familia. Sensibilidad a extremos, influencia,
   geocodificación, Puerto Madero y fuente mayoritaria; no seleccionar escenario
   por significancia ni borrar automáticamente avisos influyentes.
   Se comparan además formas cuadrática y logarítmica de distancia, con RESET
   agrupado para cada forma. Los contrastes finitos de sumar 100 m desde
   P25/P50/P75 usan la matriz de covarianza agrupada y referencia t; sus IC son
   puntuales. R²/AIC son ajuste interno, no precisión predictiva.

La matriz de evidencia identifica estimador y unidad de efecto (rho o % por 100 m)
para no comparar magnitudes incompatibles. Los datos son observacionales y la
auditoría es retrospectiva: las familias transparentan esta revisión, no son un
prerregistro. IC puntuales no son intervalos simultáneos; la autocorrelación y la
captura por portales impiden prometer niveles poblacionales de error nominal.
Los folds LOO comparten entrenamiento: los contrastes de errores son exploratorios.

## Reproducir

Con el entorno editable ya instalado y los insumos de 01–07 disponibles:

```bash
python -m unittest discover -s tests -v
python -m src.run_notebooks_sequential --start 8 --end 16
```

Para reconstruir desde las fuentes versionadas:

```bash
python -m src.run_notebooks_sequential
```

Las tablas y figuras nuevas de 16 se guardan en
`data/processed/reports/robustez_pe3/`. Las pruebas automatizadas usan casos
sintéticos con asociación conocida, confusión conocida, valores degenerados y
geografía sin soporte; comprueban además que el objetivo del barrio evaluado no
se filtre a su propia predicción LOO.

## Validación técnica de esta revisión (31/10/2026)

- Notebooks 08–16 ejecutados: 79 celdas de código, ninguna salida de tipo error;
  61 imágenes PNG embebidas entre los nueve notebooks.
- Once pruebas automatizadas aprobadas, incluidas importaciones desde otra
  carpeta, casos degenerados, confusión conocida, aislamiento LOO, igualdad de
  referencia del clustering y recuperación de una asociación de precios conocida.
- Se revisaron visualmente los paneles de hipótesis y las sensibilidades de H3.
- README, fuentes crudas y notebooks 01–07 sin cambios. Esas etapas habían sido
  ejecutadas en la validación técnica anterior; esta revisión reejecuta las
  etapas analíticas modificadas y el nuevo notebook transversal.
- Las interpretaciones son provisionales. El paso posterior es acordar su
  formulación final, la narrativa de entrega y el dashboard visual.
