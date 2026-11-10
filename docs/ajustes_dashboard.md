# Ajustes del informe de Power BI

Responsable: equipo del dashboard. El repositorio prepara datos y medidas; no modifica el PBIX ni el informe publicado. Presentación PPT a cargo del equipo de exposición.

## Importación y tarjetas de precios

1. Reimportar `dashboard_mart` o el ZIP final. Actualizar tipos desde `powerbi/esquema_powerbi.json` y relaciones desde `relaciones.csv`. CSV UTF-8, decimal punto. Mantener filtros de dimensiones hacia hechos 1:N; no unir hechos entre sí.
2. Copiar las medidas de `powerbi/medidas_dax.dax`. Venta USD/m² y alquiler USD/m²/mes usan `MEDIAN(fact_publicacion[precio_m2_dashboard])` con operación correspondiente. Alquiler mensual usa `precio_mensual_dashboard`; venta total usa `precio_venta_dashboard`. No usar AVERAGE sobre `fact_kpi_barrio` ni la columna `precio` sin conversión.
3. Mostrar `N venta m2`, `N alquiler m2` o `N alquiler mensual` junto a la tarjeta correspondiente. El n debe contar valores no nulos del mismo campo y universo, no todas las publicaciones de la página.
4. Para control inicial quitar filtros de barrio, comuna, fuente y moneda. Comparar mediana y n con `reports/control_tarjetas_dashboard.csv`. Después probar una comuna, un barrio y una fuente, comparando contra los avisos del mart bajo los mismos filtros. Mantener contexto de operación con KEEPFILTERS.
5. Las columnas aptas para tarjetas aplican `en_alcance_territorial`: mismo universo que KPIs de 07–08. `Publicaciones observadas` suma el conteo territorial; el hecho también conserva todos los avisos y su conteo original para auditoría.
6. Leyenda: «Precios pedidos en USD: USD original o ARS/MEP por fecha. Airbnb: cotización de 30 noches. Excluye valores fuera de rango; no incluye necesariamente gastos». Evitar un filtro por moneda original USD como predeterminado: descartaría avisos ARS ya convertidos.

## H1 y listas

- En la página de concentración temporaria rotular el contraste H1 como «Airbnb / alquiler permanente (avisos)». Usar la medida del mismo nombre. El cociente es de sumas; si denominador es cero, BLANK. Airbnb/km² puede conservarse en otro mapa, con su propio rótulo, sin atribuirle los rho del ratio.
- Para H4 separar precio y disponibilidad. Texto: «co-ubicación de ofertas; no evidencia de sustitución». No conservar semáforo de tres condiciones simultáneas.
- Cargar `reports/listas_operativas_comunas.csv` como tabla de consulta independiente. No relacionarla directamente a hechos; si se relaciona con dim_comuna, hacerlo 1:N y sin relaciones bidireccionales. Filtrar una decisión y mostrar comuna, puesto, indicador, n, IC y rango de puestos. No sumar sus tres filas por comuna como si fueran avisos.
- En monitoreo ampliar a barrio con `brechas_monitoreo.csv`; separar Airbnb y Mercado Libre, mostrar ambos n y advertencia de productos distintos.

## Scatter de precios

- Eje X: `superficie_dashboard_m2`, sin sumar superficies entre avisos; detalle por fuente × id × operación. Excluir BLANK. Rango visual 10–2.000 m²; no modifica la base ni la tarjeta. No usar superficie sin validar.
- Eje Y: precio válido de la operación seleccionada. Venta y alquiler no comparten unidad temporal; usar selector o paneles separados.
- Ejes con unidades «m²» y «USD/m²» o «USD/m²/mes». Unidades de visualización: Ninguna; evitar «100,000 mil» y «0,001 mil». Mostrar conteo antes y después del recorte en tooltip o nota.

## Nombres, ejes y tooltips

- Nombres visibles: `alquiler_temporal` → «Alquiler temporario»; `alquiler` → «Alquiler permanente»; `venta` → «Venta». Cambiar el nombre visible, no la clave de las tablas.
- `Valor_Mapa` → nombre y unidad del indicador seleccionado. Título dinámico consistente con servicio, operación y denominador.
- Comuna: eje categórico/discreto, orden numérico 1–15; no eje continuo ni interpolación.
- Tooltips: barrio/comuna, operación, indicador con unidad, n del mismo universo y regla de moneda. Quitar claves, columnas auxiliares, sumas automáticas y duplicaciones de etiquetas.
- Donde las categorías sean pocas, preferir etiquetas de datos legibles; no duplicar información con un eje de escala confusa. Conservar unidad y precisión útil.

## Criterio de cierre por el equipo

Verificar filtros sin selección y selecciones de comuna/barrio/fuente; mediana y n deben coincidir con el cálculo directo. Revisar rótulo H1, ejes, outliers visibles, moneda y tooltips. Registrar fecha, versión/commit de mart y capturas de cada página modificada. Actualizar el estado del README únicamente después de comparar el informe publicado. Usar esos mismos valores en PPT. Este documento no certifica que los cambios ya estén publicados.
