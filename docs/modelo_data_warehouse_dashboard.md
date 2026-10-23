# Modelo dimensional para el dashboard PE3

El mart separa tablas de hechos por granularidad. No se unen hechos directamente: las dimensiones filtran cada hecho en relaciones 1:N con filtro unidireccional. La geografía usa una jerarquía normalizada `dim_comuna → dim_barrio`; los hechos barriales se conectan solo al barrio.

```mermaid
erDiagram
    dim_fecha ||--o{ fact_publicacion : fecha
    dim_fuente ||--o{ fact_publicacion : fuente
    dim_operacion ||--o{ fact_publicacion : operacion
    dim_tipo_propiedad ||--o{ fact_publicacion : tipologia
    dim_moneda ||--o{ fact_publicacion : moneda
    dim_comuna ||--o{ dim_barrio : jerarquia
    dim_barrio ||--o{ fact_publicacion : barrio
    dim_barrio ||--o{ fact_barrio_operacion : barrio
    dim_operacion ||--o{ fact_barrio_operacion : operacion
    dim_barrio ||--o{ fact_kpi_barrio : barrio
    dim_comuna ||--o{ fact_comuna_operacion : comuna
    dim_operacion ||--o{ fact_comuna_operacion : operacion
    dim_comuna ||--o{ fact_kpi_comuna : comuna
    dim_barrio ||--o{ fact_contexto_barrio : barrio
    dim_comuna ||--o{ fact_censo_comuna : comuna
```

## Granularidad

| Tabla | Una fila representa |
|---|---|
| `fact_publicacion` | fuente × id × operación |
| `fact_barrio_operacion` | barrio × corte PE2 × operación |
| `fact_kpi_barrio` | barrio × corte PE2 |
| `fact_comuna_operacion` | comuna × corte PE2 × operación |
| `fact_kpi_comuna` | comuna × corte PE2, métricas de mercado |
| `fact_contexto_barrio` | barrio × versión de contexto |
| `fact_censo_comuna` | comuna × Censo 2022 |

## Medidas, relaciones y límites

- Conteos de anuncios miden oferta capturada, no stock de viviendas ni contratos.
- Precios son no aditivos: usar mediana/percentiles, segmentados por operación y moneda. No promediar o sumar publicaciones para inferir valor transaccional.
- Ratios y densidades se consumen en su grano; no promediar porcentajes ni repetir denominadores censales a nivel de publicación.
- Airbnb es un indicador de alquiler temporario y queda diferenciable de la oferta inmobiliaria tradicional según cobertura de las fuentes.
- El Censo y el tamaño medio del hogar se mantienen a nivel comuna; este último es un proxy indirecto para H2a.
- La fecha de extracción no crea una serie temporal de snapshots. No mostrar evolución temporal con un único corte.
- La dimensión barrio almacena `comuna_key`; KPIs y publicaciones barriales se filtran por comuna a través de la jerarquía comuna → barrio. Se evita una segunda FK comuna directa en el hecho de publicaciones para mantener una sola ruta de filtro.
- Las publicaciones sin barrio oficial asignado no participan de un filtro comunal desde `dim_barrio`; medir y mostrar esa cobertura antes de interpretar totales territoriales.
- Las dimensiones geográficas actuales reflejan este corte. Para comparar futuras cargas, usar códigos oficiales estables o versionar cambios de nombres/correspondencias.
- El constructor valida la clave fuente × id × operación y se detiene si encuentra duplicados, en vez de ocultarlos.
- Ejecución: `python src/build_dashboard_mart.py`. Produce CSV por tabla y `data_model.json` con granos, columnas y número de filas.