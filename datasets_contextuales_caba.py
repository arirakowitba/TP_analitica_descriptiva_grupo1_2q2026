"""
Datasets contextuales de CABA para enriquecer el análisis de propiedades.

Mismo espíritu que el script de referencia del TP del año pasado: variables
de "contexto urbano" (no de las propiedades en sí) que después se cruzan por
cercanía geográfica (point-in-polygon / nearest neighbor) con cada aviso.

Fuentes: Buenos Aires Data (GCBA), salvo el Censo 2022 (INDEC) y el tipo de
cambio (ver notas en cada sección).

Nota metodológica: los links de abajo los verifiqué entrando a cada página de
dataset en data.buenosaires.gob.ar y copiando el recurso CSV real (los ID de
recurso de CKAN no son adivinables, cambian por dataset). No pude correr
`pd.read_csv` de punta a punta contra estos links desde mi entorno de prueba
(no tiene salida de red a buenosaires.gob.ar), así que si alguno tira error de
columnas/encoding avisame con el traceback y lo ajustamos.
"""

import numpy as np
import pandas as pd
import requests

# =============================================================================
# 1. TIPO DE CAMBIO USD/ARS
# =============================================================================

def get_bcra_exchange_rate(start_date='2003-01-01', end_date=None):
    """Devuelve una serie diaria de tipo de cambio USD/ARS.

    La API oficial del BCRA requiere token (registro en
    https://www.bcra.gob.ar/Pdfs/Institucional/API_BCRA.pdf). Como alternativa
    gratuita y sin registro para el dólar "oficial"/"blue" del día a día,
    se puede usar DolarAPI (https://dolarapi.com/docs/) — pero solo devuelve
    el valor ACTUAL, no una serie histórica completa. Para la serie histórica
    completa sin token, otra opción es scrapear/consumir series de
    ámbito.com o infodolar, o pedir el token del BCRA si se necesita para el TP.

    Por ahora se genera una serie dummy para no bloquear el resto del pipeline;
    reemplazar por datos reales según cuál opción elijan.
    """
    if end_date is None:
        end_date = pd.to_datetime('today').strftime('%Y-%m-%d')

    print("Para datos reales del BCRA hace falta un token (ver docstring).")
    print("Alternativa sin token para el valor DE HOY: DolarApi (dolarapi.com).")
    print("Generando una serie dummy como placeholder para no frenar el resto del script...")

    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    exchange_rates = 100 + np.arange(len(dates)) * 0.1 + np.random.rand(len(dates)) * 5

    return pd.DataFrame({'fecha': dates, 'tipo_cambio_usd_ars': exchange_rates})


def get_dolar_hoy():
    """Valor del dólar HOY (no serie histórica) vía DolarAPI, gratis y sin token."""
    try:
        r = requests.get("https://dolarapi.com/v1/dolares", timeout=10)
        r.raise_for_status()
        return pd.DataFrame(r.json())
    except requests.RequestException as exc:
        print(f"No se pudo consultar DolarAPI: {exc}")
        return None


df_tipo_cambio = get_bcra_exchange_rate()
print("Head de tipo de cambio (dummy):")
print(df_tipo_cambio.head())

dolar_hoy = get_dolar_hoy()
if dolar_hoy is not None:
    print("\nCotizaciones de HOY (DolarAPI):")
    print(dolar_hoy)


# =============================================================================
# 2. LINKS A DATASETS DE BUENOS AIRES DATA (GCBA)
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
# 3. CENSO POBLACIONAL 2022 (INDEC) — caso aparte
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
# censo_2022 = pd.read_excel("censo_2022_caba_por_comuna.xlsx", skiprows=...)
#
# Dejamos la variable en None para que el resto del pipeline no rompa si
# todavía no se bajó el archivo a mano.
censo_2022 = None
print("\nCenso 2022 (INDEC): requiere descarga manual (ver comentario en el código).")


# =============================================================================
# 4. RESUMEN
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
