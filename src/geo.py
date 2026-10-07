"""Utilidades geográficas sin dependencias GIS pesadas.

- Conversión de coordenadas planas de CABA (Gauss-Krüger) a grados WGS84.
- Parseo de geometrías WKT (POINT, POLYGON, MULTIPOLYGON).
- Asignación de puntos a barrios (punto en polígono).
- Distancia al punto más cercano y conteo en radio (BallTree haversine).
"""

import json
import re

import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath
from sklearn.neighbors import BallTree

RADIO_TIERRA_M = 6_371_000
BBOX_CABA = {'lat': (-34.72, -34.52), 'lon': (-58.54, -58.33)}

# Proyecciones transversas de Mercator de CABA: (lat origen, lon origen, falso este, falso norte).
# Ambas usan el origen de Gauss-Krüger BA y difieren en el falso origen:
#   'gkba': devuelto por el geocodificador REST de USIG (100.000 / 100.000).
#   'gkba_ba_data': recursos de BA Data en metros (hospitales, educación, bibliotecas) (20.000 / 70.000).
# Validación: contra el servicio `normalizar` de USIG (WGS84) el error es de 1-2 m, y las 2.763
# escuelas caen en el barrio que declaran en el 100% de los casos. Con el origen de EPSG:9498
# (-34.6297166, -58.4627) los puntos quedaban corridos ~51 m al sur y ~56 m al este.
SISTEMAS = {
    'gkba': (-34.629269, -58.4633, 100_000, 100_000),
    'gkba_ba_data': (-34.629269, -58.4633, 20_000, 70_000),
}

# Elipsoide WGS84.
_A, _E2 = 6_378_137.0, 0.00669437999


def planas_a_wgs84(x, y, sistema):
    """Convierte coordenadas planas (metros) a (lat, lon) en grados.

    Aproximación local alrededor del origen: dentro de CABA (radio < 15 km) el error
    es de pocos metros, despreciable frente a los radios de 500 m que se usan después.
    """
    lat0, lon0, fe, fn = SISTEMAS[sistema]
    s2 = np.sin(np.radians(lat0)) ** 2
    radio_meridiano = _A * (1 - _E2) / (1 - _E2 * s2) ** 1.5
    radio_primer_vertical = _A / np.sqrt(1 - _E2 * s2)
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    lat = lat0 + np.degrees((y - fn) / radio_meridiano)
    lon = lon0 + np.degrees((x - fe) / (radio_primer_vertical * np.cos(np.radians(lat0))))
    return lat, lon


def a_numero(serie):
    """Convierte a float aceptando coma decimal."""
    return pd.to_numeric(serie.astype(str).str.replace(',', '.', regex=False).str.strip(), errors='coerce')


def parsear_wkt_point(serie):
    """Extrae (x, y) de geometrías 'POINT (x y)'. Devuelve dos arrays float."""
    xy = serie.astype(str).str.extract(r'POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)')
    return xy[0].astype(float).to_numpy(), xy[1].astype(float).to_numpy()


def parsear_wkt_vertices(wkt):
    """Devuelve un array (n, 2) [lon, lat] con todos los vértices de un POLYGON/MULTIPOLYGON."""
    nums = re.findall(r'(-?\d+\.?\d*)\s+(-?\d+\.?\d*)', str(wkt))
    return np.array(nums, dtype=float) if nums else np.empty((0, 2))


def en_caba(lat, lon):
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    return ((lat >= BBOX_CABA['lat'][0]) & (lat <= BBOX_CABA['lat'][1])
            & (lon >= BBOX_CABA['lon'][0]) & (lon <= BBOX_CABA['lon'][1]))


# ---------------------------------------------------------------------------
# Barrios
# ---------------------------------------------------------------------------

def cargar_barrios(ruta_geojson):
    """Tabla de los 48 barrios oficiales con comuna, área (km2) y anillos exteriores."""
    geo = json.loads(ruta_geojson.read_text(encoding='utf-8'))
    filas = []
    for feat in geo['features']:
        props = feat['properties']
        geom = feat['geometry']
        if geom['type'] == 'Polygon':
            anillos = [geom['coordinates'][0]]
        else:  # MultiPolygon
            anillos = [poly[0] for poly in geom['coordinates']]
        filas.append({
            'barrio_oficial': props['nombre'],
            'comuna': int(props['comuna']),
            'area_km2': props['area_metro'] / 1e6,
            '_paths': [MplPath(np.asarray(a)[:, :2]) for a in anillos],
        })
    return pd.DataFrame(filas)


def asignar_barrio(lat, lon, barrios):
    """Barrio oficial de cada punto (NaN si cae fuera de los 48 polígonos)."""
    pts = np.column_stack([np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)])
    validos = np.isfinite(pts).all(axis=1)
    asignado = np.full(len(pts), -1)
    for k, paths in enumerate(barrios['_paths']):
        for path in paths:
            pendientes = validos & (asignado == -1)
            if not pendientes.any():
                break
            dentro = path.contains_points(pts[pendientes])
            idx = np.flatnonzero(pendientes)[dentro]
            asignado[idx] = k
    nombres = barrios['barrio_oficial'].to_numpy()
    return pd.Series(np.where(asignado >= 0, nombres[np.clip(asignado, 0, None)], None), dtype='object')


# ---------------------------------------------------------------------------
# Distancias y conteos
# ---------------------------------------------------------------------------

def _arbol(lat, lon):
    return BallTree(np.radians(np.column_stack([lat, lon])), metric='haversine')


def distancia_minima_m(lat_pub, lon_pub, lat_ext, lon_ext):
    """Distancia en línea recta (m) desde cada publicación al punto externo más cercano.

    Devuelve NaN para publicaciones sin coordenadas válidas en CABA.
    """
    lat_pub = np.asarray(lat_pub, dtype=float)
    lon_pub = np.asarray(lon_pub, dtype=float)
    out = np.full(len(lat_pub), np.nan)
    ok = en_caba(lat_pub, lon_pub)
    if ok.any():
        dist, _ = _arbol(lat_ext, lon_ext).query(np.radians(np.column_stack([lat_pub[ok], lon_pub[ok]])), k=1)
        out[ok] = dist[:, 0] * RADIO_TIERRA_M
    return out


def conteo_en_radio(lat_pub, lon_pub, lat_ext, lon_ext, radio_m):
    """Cantidad de puntos externos a menos de `radio_m` metros de cada publicación."""
    lat_pub = np.asarray(lat_pub, dtype=float)
    lon_pub = np.asarray(lon_pub, dtype=float)
    out = np.full(len(lat_pub), np.nan)
    ok = en_caba(lat_pub, lon_pub)
    if ok.any():
        out[ok] = _arbol(lat_ext, lon_ext).query_radius(
            np.radians(np.column_stack([lat_pub[ok], lon_pub[ok]])), r=radio_m / RADIO_TIERRA_M, count_only=True)
    return out


def pct_varianza_intra(df, valor, grupo):
    """Porcentaje de la varianza de `valor` que ocurre dentro de los grupos (1 - SSB/SST)."""
    d = df[[valor, grupo]].dropna()
    if len(d) < 2:
        return np.nan
    media = d[valor].mean()
    sst = ((d[valor] - media) ** 2).sum()
    ssb = d.groupby(grupo)[valor].agg(lambda s: len(s) * (s.mean() - media) ** 2).sum()
    return round(100 * (1 - ssb / sst), 1) if sst > 0 else np.nan
