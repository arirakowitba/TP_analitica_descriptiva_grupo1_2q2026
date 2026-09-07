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
    pipeline si un solo dataset falla. Reintenta con distintos encodings:
    varios datasets de BA Data vienen en Latin-1/Windows-1252 en vez de
    UTF-8 (típico en archivos generados desde Excel), y con distinto
    separador (';' en vez de ',')."""
    intentos = [
        {"encoding": "utf-8"},
        {"encoding": "latin-1"},
        {"encoding": "cp1252"},
        {"encoding": "latin-1", "sep": ";"},
        {"encoding": "utf-8", "sep": ";"},
    ]
    ultimo_error = None
    for kwargs in intentos:
        try:
            df = pd.read_csv(url, **kwargs)
            if df.shape[1] == 1 and "sep" not in kwargs:
                # Probablemente el separador real es ';' y no ',' -> seguir probando.
                continue
            print(f"OK  {nombre}: {len(df)} filas, {df.shape[1]} columnas. ({kwargs})")
            return df
        except Exception as exc:
            ultimo_error = exc
            continue
    print(f"ERROR al leer '{nombre}' desde {url}\n  -> {ultimo_error}")
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
# descarga como un CSV plano de una URL fija: se descargan planillas por
# comuna desde https://censo.gob.ar/index.php/datos_definitivos_caba/
# en formato Excel, con estructura jerárquica y varias filas de
# título/metadata antes de la tabla real.
#
# El archivo 'c2022_caba_est_c2_1.xlsx' (Cuadro 2.1: Total de población y
# densidad, por superficie, según comuna) tiene esta estructura verificada:
#   - Hoja: "Cuadro 2.1"
#   - Filas 0-4: títulos y encabezado repartido en 3 sub-filas
#   - Filas 5-20: datos (fila 5 = "Total" de la Ciudad, filas 6-20 = Comuna 1 a 15)
#   - Filas 21 en adelante: notas al pie (Ley de Comunas, fuentes, etc.)
try:
    censo_2022 = pd.read_excel(
        "c2022_caba_est_c2_1.xlsx",
        sheet_name="Cuadro 2.1",
        skiprows=5,
        header=None,
        nrows=16,
        usecols="A:E",
        names=["codigo_comuna_indec", "comuna", "superficie_km2",
               "poblacion_total", "densidad_hab_km2"],
    )
    # La primera fila es el total de la Ciudad, no una comuna -> aparte.
    censo_2022_total_ciudad = censo_2022.iloc[[0]].copy()
    censo_2022 = censo_2022.iloc[1:].copy()
    # "Comuna 1" -> 1 (entero), para poder cruzar con la columna 'comuna'
    # numérica que ya tenés en ArgenProp/Zonaprop/Meli.
    censo_2022["numero_comuna"] = (
        censo_2022["comuna"].str.extract(r"(\d+)").astype(int)
    )
    print(f"\nCenso 2022 (INDEC) cargado: {len(censo_2022)} comunas.")
except FileNotFoundError:
    censo_2022 = None
    censo_2022_total_ciudad = None
    print("\nCenso 2022 (INDEC): no se encontró 'c2022_caba_est_c2_1.xlsx' en el "
          "directorio de trabajo. Subilo o ajustá la ruta.")


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
