"""Geocodificación de direcciones de CABA con los servicios de USIG (GCBA), con caché local.

Dos servicios, según el tipo de dirección:
- calle y altura: endpoint REST `normalizar_y_geocodificar_direcciones` (rápido, ~0,3 s),
  que devuelve coordenadas planas Gauss-Krüger BA; se convierten a grados con `geo`.
- intersecciones ("Cabello y Lafinur"): servicio `normalizar`, que las admite y devuelve
  WGS84, pero tiene latencia muy variable; se usa con timeout y reintentos.

Cada consulta se guarda en `data/processed/geocodificacion_usig_cache.csv`. Con la caché
completa, los notebooks no hacen ninguna llamada de red.

Uso por línea de comandos (corrida única, ~1 h):
    python -m src.usig
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from .config import BASE_CONSOLIDADA, CACHE_GEOCODIFICACION
from . import geo

URL_REST = 'https://ws.usig.buenosaires.gob.ar/rest/normalizar_y_geocodificar_direcciones'
URL_NORMALIZAR = 'https://servicios.usig.buenosaires.gob.ar/normalizar/'
COLUMNAS_CACHE = ['clave', 'tipo', 'calle', 'altura', 'cruce', 'estado', 'metodo',
                  'direccion_normalizada', 'lat', 'lon', 'fecha_consulta_utc']

_PATRON_CRUCE = re.compile(r'\s+(?:y|e|esq\.?|esquina)\s+', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Limpieza de direcciones
# ---------------------------------------------------------------------------

def limpiar_direccion(calle, altura):
    """Devuelve (tipo, calle, altura, cruce) listo para consultar, o None si no es geocodificable.

    tipo es 'calle_altura' o 'interseccion'. Reglas, en orden:
    - descarta sufijos de unidad o descripción (" - Unidad 4A", " - 2 Ambientes ...");
    - corta en "Entre ..." (referencia de cuadra, no parte de la calle);
    - descarta piso y departamento ("5° A");
    - quita el conector " Al" que usa Mercado Libre ("Thames Al" + 600);
    - si falta la altura, la toma del propio texto ("Campichuelo Al 450"), evitando
      calles con números en el nombre ("9 De Julio");
    - sin altura válida, intenta interpretarla como intersección ("Pavon Y Alberti").
    """
    c = '' if calle is None or (isinstance(calle, float) and np.isnan(calle)) else str(calle).strip()
    if not c or c.lower() == 'nan':
        return None
    c = re.sub(r'\s+-\s+.*$', '', c)
    c = re.split(r'\bentre\b', c, flags=re.IGNORECASE)[0]
    c = re.sub(r'\d+\s*°.*$', '', c)
    c = re.sub(r'["\']', '', c)
    c = re.sub(r'[.,;:]+\s*$', '', c).strip()

    try:
        alt = int(float(altura))
    except (TypeError, ValueError):
        alt = 0

    if alt <= 0:
        m = re.match(r'^(?P<calle>.+?)\s+(?:al\s+)?(?P<alt>\d{2,5})\b(?!\s*de\b)', c, flags=re.IGNORECASE)
        if m:
            c, alt = m.group('calle'), int(m.group('alt'))
    c = re.sub(r'\s+al$', '', c, flags=re.IGNORECASE).strip()

    if alt > 0 and c:
        return ('calle_altura', c, alt, None)
    partes = _PATRON_CRUCE.split(c, maxsplit=1)
    if len(partes) == 2 and all(len(p.strip()) >= 3 for p in partes):
        return ('interseccion', partes[0].strip(), None, partes[1].strip())
    return None


def clave_direccion(tipo, calle, altura, cruce):
    return f"{tipo}|{calle.lower()}|{altura or ''}|{(cruce or '').lower()}"


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def _consultar_calle_altura(calle, altura, sesion):
    """Prueba la calle completa y, si falla, sus últimas dos y una palabra.

    El reintento cubre textos con prefijos de título ("Departamento En Venta En Recoleta
    Ayacucho"); el resultado se valida luego contra el barrio declarado.
    """
    palabras = calle.split()
    intentos = [calle]
    if len(palabras) > 2:
        intentos += [' '.join(palabras[-2:]), palabras[-1]]
    ultimo = 'sin_resultado'
    for i, intento in enumerate(intentos):
        if len(intento) < 3:
            continue
        r = sesion.get(URL_REST, params={'calle': intento, 'altura': altura, 'desambiguar': 1}, timeout=30)
        if r.status_code != 200 or not r.text.startswith('{'):
            ultimo = f'http_{r.status_code}'
            continue
        data = r.json()
        gc = data.get('GeoCodificacion')
        if isinstance(gc, str):  # calle normalizada pero sin ubicación: el servicio devuelve el error como texto
            ultimo = gc
            continue
        gc = gc or {}
        if gc.get('x') and gc.get('y'):
            lat, lon = geo.planas_a_wgs84(float(gc['x']), float(gc['y']), 'gkba')
            dirs = data['Normalizacion'].get('DireccionesCalleAltura', {}).get('direcciones', [])
            normalizada = f"{dirs[0]['Calle']} {dirs[0]['Altura']}" if dirs else None
            metodo = 'rest_calle_altura' if i == 0 else 'rest_calle_altura_recortada'
            return 'ok', metodo, normalizada, float(lat), float(lon)
        ultimo = data.get('Normalizacion', {}).get('TipoResultado', 'sin_resultado')
    return ultimo, None, None, np.nan, np.nan


def _consultar_interseccion(calle, cruce, sesion, reintentos=2):
    ultimo = 'sin_resultado'
    for _ in range(reintentos + 1):
        try:
            r = sesion.get(URL_NORMALIZAR, params={'direccion': f'{calle} y {cruce}', 'geocodificar': 'TRUE',
                                                   'srid': 4326}, timeout=45)
        except requests.RequestException as exc:
            ultimo = type(exc).__name__
            continue
        if r.status_code != 200:
            ultimo = f'http_{r.status_code}'
            time.sleep(2)
            continue
        candidatos = [d for d in r.json().get('direccionesNormalizadas', [])
                      if d.get('cod_partido') == 'caba' and d.get('coordenadas')]
        if not candidatos:
            return 'sin_resultado', None, None, np.nan, np.nan
        d = candidatos[0]
        return ('ok', 'normalizar_interseccion', d.get('direccion'),
                float(d['coordenadas']['y']), float(d['coordenadas']['x']))
    return ultimo, None, None, np.nan, np.nan


def _geocodificar_uno(fila, sesion):
    try:
        if fila['tipo'] == 'calle_altura':
            res = _consultar_calle_altura(fila['calle'], fila['altura'], sesion)
        else:
            res = _consultar_interseccion(fila['calle'], fila['cruce'], sesion)
    except Exception as exc:  # error de red puntual: queda registrado y se puede reintentar
        res = (f'error_{type(exc).__name__}', None, None, np.nan, np.nan)
    estado, metodo, normalizada, lat, lon = res
    if estado == 'ok' and not geo.en_caba(lat, lon):
        estado = 'fuera_de_caba'
    return {**fila, 'estado': estado, 'metodo': metodo, 'direccion_normalizada': normalizada,
            'lat': lat, 'lon': lon, 'fecha_consulta_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')}


# ---------------------------------------------------------------------------
# Caché y lotes
# ---------------------------------------------------------------------------

def leer_cache(ruta=CACHE_GEOCODIFICACION):
    if ruta.exists():
        return pd.read_csv(ruta, dtype={'clave': str})
    return pd.DataFrame(columns=COLUMNAS_CACHE)


def preparar_consultas(df, col_calle='calle', col_altura='altura'):
    """Agrega a `df` las columnas geo_tipo y geo_clave, y devuelve las consultas únicas."""
    limpias = [limpiar_direccion(c, a) for c, a in zip(df[col_calle], df[col_altura])]
    df['geo_tipo'] = [l[0] if l else None for l in limpias]
    df['geo_clave'] = [clave_direccion(*l) if l else None for l in limpias]
    consultas = pd.DataFrame([{'clave': clave_direccion(*l), 'tipo': l[0], 'calle': l[1], 'altura': l[2],
                               'cruce': l[3]} for l in limpias if l])
    consultas['altura'] = consultas['altura'].astype('Int64')
    return consultas.drop_duplicates('clave').reset_index(drop=True)


def geocodificar_lote(consultas, ruta_cache=CACHE_GEOCODIFICACION, workers=4, reintentar_errores=True,
                      guardar_cada=500):
    """Geocodifica las consultas que no están en caché y devuelve la caché completa."""
    cache = leer_cache(ruta_cache)
    if reintentar_errores and len(cache):
        cache = cache[~cache['estado'].astype(str).str.startswith(('error_', 'http_'))]
    pendientes = consultas[~consultas['clave'].isin(cache['clave'])]
    print(f'Consultas únicas: {len(consultas)} | en caché: {len(consultas) - len(pendientes)} | '
          f'pendientes: {len(pendientes)}')
    if pendientes.empty:
        return cache

    nuevos = []
    t0 = time.time()
    with requests.Session() as sesion, ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = [pool.submit(_geocodificar_uno, fila, sesion) for fila in pendientes.to_dict('records')]
        for i, fut in enumerate(as_completed(futuros), 1):
            nuevos.append(fut.result())
            if i % guardar_cada == 0 or i == len(futuros):
                cache = pd.concat([cache, pd.DataFrame(nuevos)], ignore_index=True)
                cache.to_csv(ruta_cache, index=False)
                nuevos = []
                ok = (cache['estado'] == 'ok').mean() * 100
                print(f'  {i}/{len(futuros)} procesadas | {time.time() - t0:.0f} s | ok en caché: {ok:.1f} %',
                      flush=True)
    return cache


if __name__ == '__main__':
    base = pd.read_csv(BASE_CONSOLIDADA, low_memory=False, usecols=['fuente_norm', 'calle', 'altura'])
    base = base[base['fuente_norm'] != 'airbnb'].copy()
    geocodificar_lote(preparar_consultas(base))
