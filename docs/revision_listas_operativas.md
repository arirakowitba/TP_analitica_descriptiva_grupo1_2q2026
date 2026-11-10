# Revisión de primeros puestos

Revisión de consistencia sobre tablas y avisos del repositorio; no es inspección de inmuebles ni validación administrativa del stock. Fecha: 10 de noviembre de 2026. Reproducir con 07 y 09; el detalle numérico vigente está en `reports/listas_operativas_comunas.csv` y `brechas_monitoreo.csv`.

## Monitoreo del temporario

**Comunas 14, 1, 2 y 13.** Encabezan la intensidad Airbnb/1.000 viviendas y también concentran precios altos. Los conteos de alquiler permanente son elevados, no bajos; excluirlas por no satisfacer «permanente bajo» borraría el caso que H4 permite observar. El ratio Airbnb/permanente difiere entre ellas: concentración absoluta o por viviendas y predominio relativo no son sinónimos.

Se revisaron el número de precios válidos, los flags excluidos, fuentes y monedas. Las cuatro tienen precios tanto ARS como USD; por eso la tarjeta mensual basada solo en USD cambia la población y no representa el conjunto. Mercado Libre domina alquiler, con aportes menores de ZonaProp/ArgenProp. La estabilidad frente a un shock MEP no elimina ese sesgo de captura.

**Acción:** monitorear composición por barrio y portal, registrar condiciones de estadía y gastos incluidos, y contrastar contratos/registro administrativo antes de proponer regulación. Usar brechas mensuales por ambiente como contexto; no inferir sustitución ni rentabilidad. Los IC de precios entre comunas cercanas pueden superponerse: no tratar el orden puntual como jerarquía estadística estricta.

## Baja intensidad de alquiler permanente

**Comuna 8.** Primer caso para verificar cobertura: el alquiler observado proviene íntegramente de Mercado Libre y está expresado originalmente en ARS. Su baja intensidad no demuestra escasez real. Dispone de menos precios que otras comunas; por eso puede perder elegibilidad en el escenario que exige 100 precios, aunque siga siendo válida para ordenar conteos.

**Comunas 4 y 9.** También encabezan esta lista y tienen mucha menos diversidad de fuente que las comunas de monitoreo temporario. La lectura prioritaria es completar información territorial y contrastar hogares inquilinos/Censo con un relevamiento actual. No usar el número reducido de Airbnb para descartar un problema residencial ni convertir una baja cantidad de avisos en viviendas faltantes.

**Acción:** verificar cobertura con nuevas fuentes administrativas o relevamiento y revisar publicación repetida entre portales. El denominador es hogares inquilinos del Censo 2022; la tasa no mide porcentaje de hogares que buscan vivienda en 2026.

## Precios de alquiler

**Comunas 1, 14 y 13.** Se ordenan por precio de alquiler válido por m²/mes, no por precio total ni promedio de medianas barriales. El soporte de precios es alto respecto del mínimo operativo. La comuna 1 lidera precio y la 14 concentración temporaria: cada decisión tiene un orden propio.

Se revisaron avisos sin superficie utilizable y precios marcados fuera de rango: no entran al n de USD/m², aunque puedan entrar en el conteo de oferta o en la tarjeta mensual cuando esa mensualidad es válida. Este cambio de denominador debe verse en cada tarjeta. No se eliminaron outliers de la base para mejorar el ranking.

**Acción:** revisar mezcla de tipologías, moneda y condiciones contractuales; incorporar ingresos antes de hablar de asequibilidad. Las diferencias de precio no permiten prescribir inversión ni subsidio por sí solas.

## Evidencia y sensibilidad

- `listas_operativas_comunas.csv`: valores continuos, conteos, n de precio, IC bootstrap de mediana, proporción ARS, cantidad de fuentes y rango de puestos.
- `sensibilidad_listas_operativas.csv`: cada combinación de corte, soporte y shock. La frecuencia de selección no es probabilidad poblacional.
- `brechas_monitoreo.csv`: ambas fuentes temporarias por separado, n por lado e IC del cociente de medianas por ambiente. Mínimo 30 por lado; casos insuficientes quedan declarados.
- `docs/validacion_cierre.md`: ejecución y controles efectivamente completados.

Los IC se condicionan a los anuncios capturados y no cubren anuncios omitidos, duplicación entre portales o desfase censal. Para pasar de estas listas a una política se requiere la verificación sustantiva indicada en cada caso.
