"""
Datasets contextuales de CABA para enriquecer el análisis de propiedades.
Fuentes: Buenos Aires Data (GCBA), salvo el Censo 2022.
"""

import numpy as np
import pandas as pd
import requests

# =============================================================================
# 1. LINKS A DATASETS DE BUENOS AIRES DATA (GCBA)
# Todos verificados manualmente en data.buenosaires.gob.ar el 06/09/2026.
# =============================================================================

# Bibliotecas públicas
link_bibliotecas = 'https://data.buenosaires.gob.ar/dataset/bibliotecas/resource/f0868e8c-c015-48be-bea4-fb1df64c1549/download'

# Gastronómicos turísticos (Registro de Prestadores Turísticos)
link_gastronomia = 'https://data.buenosaires.gob.ar/dataset/oferta-establecimientos-gastronomicos/resource/e66613ef-aaf4-44aa-b89c-638c431fef0e/download'

# Establecimientos educativos (gestión pública y privada)
link_educacion = 'https://data.buenosaires.gob.ar/dataset/establecimientos-educativos/resource/ea2bd89f-c680-4b7d-b5fe-1b5b0ecc6a8a/download'

# Hospitales
link_hospitales = 'https://data.buenosaires.gob.ar/dataset/hospitales/resource/955d9dad-e05c-4093-ae27-b8427f82e4bb/download'

# Espacios culturales (bares, bibliotecas, centros culturales, cines, teatros, museos, etc.)
link_espacios_culturales = 'https://data.buenosaires.gob.ar/dataset/espacios-culturales/resource/juqdkmgo-711-resource/download'

# Espacios verdes públicos (parques, plazas, plazoletas, polideportivos)
link_espacios_verdes = 'https://data.buenosaires.gob.ar/dataset/espacios-verdes/resource/df878bd5-5759-4af3-badc-2a4c1ae0ebf8/download'

# Estaciones de Subte
link_subte_estaciones = 'https://data.buenosaires.gob.ar/dataset/subte-estaciones/resource/juqdkmgo-1994-resource/download'

# Uso (pasajeros) de las líneas de Subte, por año, desde junio 2013
link_subte_pasajeros = 'https://data.buenosaires.gob.ar/dataset/subte-estaciones/resource/4c3ae32b-4639-4e83-8224-eaf32040068e/download'

# Corredores de MetroBus (link provisto en la consigna)
link_metrobus = 'https://data.buenosaires.gob.ar/dataset/metrobus/resource/Juqdkmgo-1431222-resource/download'

# Estaciones de Ferrocarril
link_estaciones_ferrocarril = 'https://data.buenosaires.gob.ar/dataset/estaciones-ferrocarril/resource/juqdkmgo-1021-resource/download'


def _leer_csv(nombre: str, url: str) -> pd.DataFrame | None:
    """Descarga y lee un CSV, con manejo de errores para no frenar todo el
    pipeline si un solo dataset falla (encoding, separador, o el recurso
    cambió de ID)."""
    try:
        df = pd.read_csv(url)
        print(f"OK  {nombre}: {len(df)} filas, {df.shape[1]} columnas.")
        return df
    except Exception as exc:
        print(f"ERROR al leer '{nombre}' desde {url}\n  -> {exc}")
        return None


bibliotecas = _leer_csv("Bibliotecas", link_bibliotecas)
gastronomia = _leer_csv("Gastronomía", link_gastronomia)
educacion = _leer_csv("Establecimientos educativos", link_educacion)
hospitales = _leer_csv("Hospitales", link_hospitales)
espacios_culturales = _leer_csv("Espacios culturales", link_espacios_culturales)
espacios_verdes = _leer_csv("Espacios verdes", link_espacios_verdes)
subte_estaciones = _leer_csv("Subte - estaciones", link_subte_estaciones)
subte_pasajeros = _leer_csv("Subte - uso/pasajeros por año", link_subte_pasajeros)
metrobus = _leer_csv("MetroBus - corredores", link_metrobus)
estaciones_ferrocarril = _leer_csv("Estaciones de ferrocarril", link_estaciones_ferrocarril)


# =============================================================================
# 2. CENSO POBLACIONAL 2022 (INDEC) — caso aparte
# =============================================================================
# A diferencia de los datasets de BA Data, el Censo 2022 del INDEC NO se
# descarga como un CSV plano de una URL fija: se consulta a través de
# REDATAM (https://redatam.indec.gob.ar) o se descargan planillas por
# provincia/radio censal desde https://censo.gob.ar/index.php/datos_definitivos_caba/
# en formato Excel, con estructura jerárquica (radio censal -> comuna).
#
# Recomendación: descargar manualmente la planilla de CABA por comuna/radio
# censal desde ese link, guardarla en este mismo directorio, y cargarla acá:
#
censo_2022 = pd.read_excel("c2022_caba_est_c2_1.xlsx", skiprows=...)


# =============================================================================
# 3. RESUMEN
# =============================================================================

datasets = {
    "bibliotecas": bibliotecas,
    "gastronomia": gastronomia,
    "educacion": educacion,
    "hospitales": hospitales,
    "espacios_culturales": espacios_culturales,
    "espacios_verdes": espacios_verdes,
    "subte_estaciones": subte_estaciones,
    "subte_pasajeros": subte_pasajeros,
    "metrobus": metrobus,
    "estaciones_ferrocarril": estaciones_ferrocarril,
    "censo_2022": censo_2022,
}

print("\n=== Resumen de carga ===")
for nombre, df in datasets.items():
    if df is None:
        print(f"{nombre:26s} -> NO CARGADO")
    else:
        print(f"{nombre:26s} -> {len(df):6d} filas, {df.shape[1]:3d} columnas")
