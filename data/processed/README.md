# Datos procesados

Esta carpeta debe contener las salidas limpias, consolidadas o enriquecidas que se usen en notebooks y analisis posteriores.

## Criterio esperado

Cada dataset procesado debe poder rastrearse hasta sus fuentes crudas e indicar:

- archivos crudos utilizados;
- fecha o version de procesamiento;
- filtros aplicados;
- columnas creadas o transformadas;
- registros eliminados, corregidos o imputados;
- limitaciones conocidas.

## Estado actual

Esta carpeta contiene las salidas generadas por los notebooks:

- datasets preprocesados por fuente y tipo de operacion;
- bases consolidadas para EDA;
- diccionarios de datos;
- reportes tecnicos dentro de `reports/`.

Los notebooks deben vivir en `notebooks/`. Esta carpeta queda reservada para datos procesados y anexos reproducibles.
