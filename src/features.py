"""Variables derivadas: barrio oficial, tipo de cambio, precios comparables, entorno urbano y KPIs."""

import json
import re
import unicodedata

import numpy as np
import pandas as pd

from .config import EXTERNAS_RAW_DIR
from . import geo


# ---------------------------------------------------------------------------
# Barrio oficial
# ---------------------------------------------------------------------------

def normalizar_texto(valor):
    if valor is None or (isinstance(valor, float) and np.isnan(valor)) or valor is pd.NA:
        return None
    t = unicodedata.normalize('NFKD', str(valor)).encode('ascii', 'ignore').decode().lower()
    t = re.sub(r'[^a-z0-9]+', ' ', t).strip()
    return t or None


# Sub-barrios y denominaciones comerciales -> barrio oficial (GeoJSON GCBA, 48 barrios).
# Solo se incluyen las equivalencias inequívocas: un sub-barrio contenido en un único barrio.
EQUIVALENCIAS_BARRIO = {
    'belgrano r': 'Belgrano', 'belgrano c': 'Belgrano', 'belgrano barrancas': 'Belgrano',
    'belgrano chico': 'Belgrano', 'barrancas de belgrano': 'Belgrano',
    'palermo nuevo': 'Palermo', 'palermo viejo': 'Palermo', 'palermo hollywood': 'Palermo',
    'palermo soho': 'Palermo', 'palermo chico': 'Palermo', 'botanico': 'Palermo', 'las canitas': 'Palermo',
    'barrio norte': 'Recoleta',
    'villa general mitre': 'Villa Gral. Mitre', 'santa rita': 'Villa Santa Rita',
    'caballito norte': 'Caballito', 'caballito sur': 'Caballito', 'parque centenario': 'Caballito',
    'flores norte': 'Flores', 'flores sur': 'Flores',
    'la paternal': 'Paternal', 'almagro norte': 'Almagro', 'almagro sur': 'Almagro',
    'once': 'Balvanera', 'centro microcentro': 'San Nicolas', 'microcentro': 'San Nicolas',
    'boca': 'La Boca', 'montserrat': 'Monserrat', 'pompeya': 'Nueva Pompeya',
}
# Denominaciones que abarcan más de un barrio oficial: no se asignan por texto.
BARRIOS_AMBIGUOS = {'congreso', 'abasto', 'distrito quartier', 'lomas de nunez', 'tribunales'}
# Localidades fuera de CABA detectadas en el barrio declarado.
LOCALIDADES_FUERA_CABA = {'la plata', 'mar del plata', 'mar de ajo', 'rosario', 'moron', 'lomas de zamora',
                          'victoria', 'posadas', 'exaltacion de la cruz', 'tigre', 'vicente lopez', 'san isidro',
                          'olivos', 'avellaneda', 'lanus', 'quilmes'}


def barrio_desde_texto(serie, barrios_oficiales):
    """Mapea el barrio declarado por el portal a uno de los 48 oficiales.

    Devuelve (barrio_oficial, estado) donde estado es 'oficial', 'equivalencia',
    'ambiguo', 'fuera_de_caba' o 'no_reconocido'.
    """
    oficiales = {normalizar_texto(b): b for b in barrios_oficiales}
    oficiales['villa general mitre'] = oficiales.get('villa gral mitre')
    barrio, estado = [], []
    for valor in serie:
        t = normalizar_texto(valor)
        if t is None:
            barrio.append(None); estado.append('sin_dato')
        elif t in oficiales:
            barrio.append(oficiales[t]); estado.append('oficial')
        elif t in EQUIVALENCIAS_BARRIO:
            barrio.append(EQUIVALENCIAS_BARRIO[t]); estado.append('equivalencia')
        elif t in BARRIOS_AMBIGUOS:
            barrio.append(None); estado.append('ambiguo')
        elif t in LOCALIDADES_FUERA_CABA:
            barrio.append(None); estado.append('fuera_de_caba')
        else:
            barrio.append(None); estado.append('no_reconocido')
    return pd.Series(barrio, index=serie.index, dtype='object'), pd.Series(estado, index=serie.index)


# ---------------------------------------------------------------------------
# Tipo de cambio
# ---------------------------------------------------------------------------

def cargar_dolar_mep():
    """Serie diaria del dólar MEP (ArgentinaDatos, casa 'bolsa'), desde el snapshot local."""
    datos = json.loads((EXTERNAS_RAW_DIR / 'dolar_mep_diario.json').read_text(encoding='utf-8'))
    mep = pd.DataFrame(datos)
    mep['fecha'] = pd.to_datetime(mep['fecha'])
    return mep[['fecha', 'compra', 'venta']].sort_values('fecha').reset_index(drop=True)


def asignar_tipo_cambio(fechas, mep):
    """Cotización MEP vendedor vigente en cada fecha.

    Si la fecha no es hábil (fin de semana o feriado) se usa la última cotización
    disponible anterior (merge_asof hacia atrás).
    """
    f = pd.DataFrame({'fecha': pd.to_datetime(fechas).dt.normalize(), '_orden': np.arange(len(fechas))})
    ok = f['fecha'].notna()
    out = pd.DataFrame({'tc_mep': np.nan, 'fecha_tc': pd.NaT}, index=range(len(f)))
    asof = pd.merge_asof(f[ok].sort_values('fecha'), mep.rename(columns={'fecha': 'fecha_tc'}),
                         left_on='fecha', right_on='fecha_tc', direction='backward')
    out.loc[asof['_orden'].to_numpy(), 'tc_mep'] = asof['venta'].to_numpy()
    out.loc[asof['_orden'].to_numpy(), 'fecha_tc'] = asof['fecha_tc'].to_numpy()
    return out['tc_mep'].to_numpy(), out['fecha_tc'].to_numpy()


def fecha_referencia_precio(df):
    """Fecha en que se observó el precio: scraped_at_utc (convertida a hora de Argentina)
    y, si falta (Airbnb), fecha_extraccion."""
    scraped = pd.to_datetime(df['scraped_at_utc'], errors='coerce', utc=True).dt.tz_convert('America/Argentina/Buenos_Aires')
    scraped = scraped.dt.tz_localize(None).dt.normalize()
    extraccion = pd.to_datetime(df['fecha_extraccion'].astype(str).str[:10], errors='coerce')
    return scraped.fillna(extraccion)


# ---------------------------------------------------------------------------
# Precios comparables
# ---------------------------------------------------------------------------

def construir_precios(df, tc_mep):
    """Variables de precio en USD.

    - precio_venta_usd: venta, precio total publicado.
    - precio_mensual_usd: alquiler permanente y temporario de portales (precio mensual publicado)
      y Airbnb (cotización de la serie de 30 noches, `precio_mensual_estimado`).
    - precio_m2_usd: venta -> USD/m2; alquiler permanente -> USD/m2/mes. No aplica a temporario
      (Airbnb no informa superficie y MeLi temporario no es comparable por m2 con el permanente).
    - precio_por_ambiente_usd: precio de venta o mensual dividido por ambientes (monoambiente = 1).
    """
    moneda = df['moneda_norm'].fillna('').astype(str).str.upper()
    precio = pd.to_numeric(df['precio'], errors='coerce')
    precio_usd = np.where(moneda == 'USD', precio, np.where(moneda == 'ARS', precio / tc_mep, np.nan))
    moneda = moneda.replace('', np.nan)

    op = df['tipo_operacion_norm']
    es_airbnb = df['fuente_norm'] == 'airbnb'
    out = pd.DataFrame(index=df.index)
    out['precio_venta_usd'] = np.where(op == 'venta', precio_usd, np.nan)
    mensual_portal = np.where(op.isin(['alquiler', 'alquiler_temporal']) & ~es_airbnb, precio_usd, np.nan)
    out['precio_mensual_usd'] = np.where(es_airbnb, pd.to_numeric(df['precio_mensual_estimado'], errors='coerce'),
                                         mensual_portal)

    superficie = pd.to_numeric(df['superficie_ref_m2'], errors='coerce').where(lambda s: s > 0)
    out['precio_m2_usd'] = np.where(op == 'venta', out['precio_venta_usd'] / superficie,
                                    np.where(op == 'alquiler', out['precio_mensual_usd'] / superficie, np.nan))

    ambientes = pd.to_numeric(df['ambientes_ref'], errors='coerce').where(lambda s: s >= 1)
    base_precio = out['precio_venta_usd'].fillna(out['precio_mensual_usd'])
    out['precio_por_ambiente_usd'] = base_precio / ambientes
    out['moneda_original'] = moneda
    return out


# Rangos de plausibilidad para validar variables derivadas (no se usan para eliminar casos).
RANGOS_PLAUSIBLES = {
    ('precio_m2_usd', 'venta'): (500, 15_000),          # USD/m2
    ('precio_m2_usd', 'alquiler'): (2, 60),             # USD/m2/mes
    ('precio_mensual_usd', 'alquiler'): (100, 15_000),
    ('precio_mensual_usd', 'alquiler_temporal'): (100, 20_000),
    ('precio_venta_usd', 'venta'): (15_000, 10_000_000),
}


def flags_rango(df):
    """Una columna booleana por variable: True si el valor cae fuera del rango plausible de su operación."""
    flags = pd.DataFrame(index=df.index)
    for (var, op), (lo, hi) in RANGOS_PLAUSIBLES.items():
        col = f'{var}_fuera_rango_flag'
        if col not in flags:
            flags[col] = False
        m = (df['tipo_operacion_norm'] == op) & df[var].notna()
        flags.loc[m, col] = ~df.loc[m, var].between(lo, hi)
    return flags


# ---------------------------------------------------------------------------
# Entorno urbano por publicación
# ---------------------------------------------------------------------------

RADIO_CONTEO_M = 500


def variables_entorno(lat, lon, fuentes, vertices_verdes):
    """Distancias (m) y conteos en radio de 500 m para cada publicación con coordenadas."""
    out = {}
    for nombre in ['subte', 'tren', 'metrobus', 'hospitales']:
        p = fuentes[nombre]
        out[f'dist_{nombre}_m'] = geo.distancia_minima_m(lat, lon, p['lat'], p['lon'])
    out['dist_espacio_verde_m'] = geo.distancia_minima_m(lat, lon, *vertices_verdes)
    out['dist_transporte_masivo_m'] = np.fmin.reduce([out['dist_subte_m'], out['dist_tren_m'],
                                                      out['dist_metrobus_m']])
    for nombre in ['culturales', 'gastronomia', 'educacion']:
        p = fuentes[nombre].dropna(subset=['lat', 'lon'])
        out[f'n_{nombre}_{RADIO_CONTEO_M}m'] = geo.conteo_en_radio(lat, lon, p['lat'], p['lon'], RADIO_CONTEO_M)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# Entorno urbano por barrio
# ---------------------------------------------------------------------------

def contexto_por_barrio(barrios, fuentes):
    """Conteo y densidad (por km2) de cada fuente puntual en los 48 barrios, más superficie verde."""
    tabla = barrios[['barrio_oficial', 'comuna', 'area_km2']].copy().set_index('barrio_oficial')
    for nombre, p in fuentes.items():
        asignado = geo.asignar_barrio(p['lat'], p['lon'], barrios)
        conteo = asignado.value_counts()
        tabla[f'n_{nombre}'] = conteo.reindex(tabla.index).fillna(0).astype(int)
        tabla[f'densidad_{nombre}_km2'] = tabla[f'n_{nombre}'] / tabla['area_km2']
        if nombre == 'espacios_verdes':
            area = p.assign(barrio=asignado.values).groupby('barrio')['area_m2'].sum()
            tabla['pct_superficie_verde'] = 100 * area.reindex(tabla.index).fillna(0) / (tabla['area_km2'] * 1e6)
    return tabla.reset_index()
