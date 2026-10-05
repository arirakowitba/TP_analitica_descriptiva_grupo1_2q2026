"""Descarga, snapshot y carga estandarizada de las fuentes externas.

Las fuentes se descargan una sola vez a `data/raw/externas/` y quedan versionadas con
su fecha de descarga y checksum en `_metadata_descarga.json`. Los notebooks leen siempre
el snapshot local, de modo que el análisis no depende de que los portales sigan
respondiendo igual. BA Data rechaza pedidos sin un user-agent de navegador, por eso
la descarga no usa `pd.read_csv(url)` directamente.
"""

import hashlib
import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from .config import CENSO_RAW_DIR, EXTERNAS_RAW_DIR, REPO_ROOT
from . import geo

try:
    # censo.gob.ar no envía la cadena completa de certificados; truststore usa el
    # almacén del sistema operativo, que sí la resuelve.
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/128.0 Safari/537.36')

# Recursos de Buenos Aires Data (GCBA). Mismos enlaces que
# Fuentes_de_enriquecimiento/datasets_contextuales_caba.py.
BA_DATA = {
    'subte_estaciones': 'https://data.buenosaires.gob.ar/dataset/subte-estaciones/resource/juqdkmgo-1994-resource/download',
    'estaciones_ferrocarril': 'https://data.buenosaires.gob.ar/dataset/estaciones-ferrocarril/resource/juqdkmgo-1021-resource/download',
    'metrobus': 'https://data.buenosaires.gob.ar/dataset/metrobus/resource/Juqdkmgo-1431222-resource/download',
    'hospitales': 'https://data.buenosaires.gob.ar/dataset/hospitales/resource/955d9dad-e05c-4093-ae27-b8427f82e4bb/download',
    'educacion': 'https://data.buenosaires.gob.ar/dataset/establecimientos-educativos/resource/ea2bd89f-c680-4b7d-b5fe-1b5b0ecc6a8a/download',
    'espacios_culturales': 'https://data.buenosaires.gob.ar/dataset/espacios-culturales/resource/juqdkmgo-711-resource/download',
    'gastronomia': 'https://data.buenosaires.gob.ar/dataset/oferta-establecimientos-gastronomicos/resource/e66613ef-aaf4-44aa-b89c-638c431fef0e/download',
    'espacios_verdes': 'https://data.buenosaires.gob.ar/dataset/espacios-verdes/resource/df878bd5-5759-4af3-badc-2a4c1ae0ebf8/download',
    'bibliotecas': 'https://data.buenosaires.gob.ar/dataset/bibliotecas/resource/f0868e8c-c015-48be-bea4-fb1df64c1549/download',
    'subte_pasajeros': 'https://data.buenosaires.gob.ar/dataset/subte-estaciones/resource/4c3ae32b-4639-4e83-8224-eaf32040068e/download',
}
URL_BARRIOS = 'https://cdn.buenosaires.gob.ar/datosabiertos/datasets/innovacion-transformacion-digital/barrios/barrios.geojson'

# Censo 2022 (INDEC), resultados definitivos CABA: https://censo.gob.ar/index.php/datos_definitivos_caba/
URL_CENSO = 'https://censo.gob.ar/wp-content/uploads/2023/11/c2022_caba_{cuadro}.xlsx'
CUADROS_CENSO = {
    'est_c2_1': 'Población total, superficie y densidad, según comuna',
    'est_c3_1': 'Población total, en viviendas particulares, colectivas y en situación de calle, según comuna',
    'vivienda_c1_1': 'Viviendas totales, particulares por condición de ocupación y colectivas, según comuna',
    'vivienda_c2_1': 'Viviendas particulares ocupadas y hogares, por cantidad de hogares, según comuna',
    'vivienda_c3_1': 'Viviendas particulares ocupadas y hogares, por tipo de vivienda, según comuna',
    'hogares_c6_1': 'Hogares por régimen de tenencia de la vivienda, según comuna',
}

# Cotización del dólar MEP ("bolsa"), serie diaria. API pública de ArgentinaDatos.
URL_DOLAR_MEP = 'https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa'

METADATA_PATH = EXTERNAS_RAW_DIR / '_metadata_descarga.json'


def _leer_metadata():
    if METADATA_PATH.exists():
        return json.loads(METADATA_PATH.read_text(encoding='utf-8'))
    return {}


def _descargar(url, destino, timeout=120):
    resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    if resp.content[:200].lower().lstrip().startswith(b'<html'):
        raise RuntimeError(f'El servidor devolvió HTML en lugar de datos: {url}')
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(resp.content)
    return {
        'url': url,
        'archivo': destino.relative_to(REPO_ROOT).as_posix(),
        'fecha_descarga_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'bytes': len(resp.content),
        'md5': hashlib.md5(resp.content).hexdigest(),
    }


def catalogo_descargas():
    """Lista (nombre, url, destino) de todos los archivos externos del proyecto."""
    items = [(nombre, url, EXTERNAS_RAW_DIR / f'{nombre}.csv') for nombre, url in BA_DATA.items()]
    items.append(('barrios_geojson', URL_BARRIOS, EXTERNAS_RAW_DIR / 'barrios.geojson'))
    items += [(f'censo_{c}', URL_CENSO.format(cuadro=c), CENSO_RAW_DIR / f'c2022_caba_{c}.xlsx') for c in CUADROS_CENSO]
    items.append(('dolar_mep', URL_DOLAR_MEP, EXTERNAS_RAW_DIR / 'dolar_mep_diario.json'))
    return items


def descargar_fuentes(forzar=False):
    """Descarga las fuentes que todavía no tienen snapshot local.

    Con `forzar=False` (por defecto) no vuelve a bajar lo que ya existe, para que
    una nueva ejecución no cambie silenciosamente los datos del análisis.
    Devuelve un DataFrame con el estado de cada archivo.
    """
    metadata = _leer_metadata()
    filas = []
    for nombre, url, destino in catalogo_descargas():
        if destino.exists() and not forzar:
            estado = 'snapshot existente'
        else:
            try:
                metadata[nombre] = _descargar(url, destino)
                estado = 'descargado'
            except Exception as exc:
                estado = f'error: {exc}'
        info = metadata.get(nombre, {})
        filas.append({'fuente': nombre, 'estado': estado, 'archivo': destino.name,
                      'fecha_descarga_utc': info.get('fecha_descarga_utc'), 'bytes': info.get('bytes'),
                      'md5': info.get('md5')})
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Carga estandarizada de fuentes puntuales
# ---------------------------------------------------------------------------
# Cada recurso de BA Data trae la ubicación en un formato distinto. Los cargadores
# devuelven siempre las columnas [fuente, nombre, categoria, lat, lon] en grados WGS84.

def _puntos(fuente, nombre, categoria, lat, lon, **extra):
    df = pd.DataFrame({'fuente': fuente, 'nombre': nombre, 'categoria': categoria,
                       'lat': np.asarray(lat, dtype=float), 'lon': np.asarray(lon, dtype=float), **extra})
    return df.reset_index(drop=True)


def _csv(nombre, **kwargs):
    return pd.read_csv(EXTERNAS_RAW_DIR / f'{nombre}.csv', encoding=kwargs.pop('encoding', 'utf-8-sig'),
                       low_memory=False, **kwargs)


def _wkt_grados(df):
    lon, lat = geo.parsear_wkt_point(df['geometry'])
    return lat, lon


def _wkt_metros_ba_data(df):
    x, y = geo.parsear_wkt_point(df['geometry'])
    return geo.planas_a_wgs84(x, y, 'gkba_ba_data')


def cargar_subte():
    df = _csv('subte_estaciones')
    return _puntos('subte', df['estacion'], 'Línea ' + df['linea'].astype(str), *_wkt_grados(df))


def cargar_tren():
    """Estaciones de ferrocarril. Incluye estaciones del conurbano: se filtran luego por polígono."""
    df = _csv('estaciones_ferrocarril')
    return _puntos('tren', df['nombre'], df['linea'], *_wkt_grados(df))


def cargar_metrobus():
    df = _csv('metrobus')
    return _puntos('metrobus', df['NOMBRE PAR'], df['CALLE'], df['Y'], df['X'])


def cargar_hospitales():
    df = _csv('hospitales')
    return _puntos('hospitales', df['nam'], df['esp'], *_wkt_metros_ba_data(df))


NIVELES_EDUCACION_COMUN = ('Nivel inicial común', 'Nivel primario común', 'Nivel secundario común')


def cargar_educacion(solo_niveles_comunes=True):
    """Establecimientos educativos. Por defecto solo inicial, primario y secundario común,
    que son los relevantes para hogares con niños; se excluyen formación profesional,
    adultos, superior y servicios complementarios."""
    df = _csv('educacion')
    if solo_niveles_comunes:
        df = df[df['nen_mde'].fillna('').str.contains('|'.join(NIVELES_EDUCACION_COMUN), regex=True)]
    return _puntos('educacion', df['nam'], df['ges'], *_wkt_metros_ba_data(df))


def cargar_culturales():
    df = _csv('espacios_culturales')
    return _puntos('culturales', df['ESTABLECIMIENTO'], df['FUNCION_PRINCIPAL'],
                   geo.a_numero(df['LATITUD']), geo.a_numero(df['LONGITUD']))


def cargar_gastronomia():
    df = _csv('gastronomia', sep=';', encoding='latin-1')
    return _puntos('gastronomia', df['nombre'], df['categoria'], geo.a_numero(df['lat']), geo.a_numero(df['long']))


CLASES_VERDE_UTILIZABLE = ('PLAZA', 'PARQUE', 'PARQUE SEMIPÚBLICO', 'JARDÍN', 'JARDÍN BOTÁNICO')


def cargar_espacios_verdes(solo_utilizables=True):
    """Espacios verdes como polígonos. Devuelve una fila por espacio con su centroide
    aproximado (promedio de vértices), su superficie (m2) y sus vértices.

    Con `solo_utilizables=True` se excluyen canteros centrales, plazoletas, patios y paseos:
    son superficies chicas o lineales que no funcionan como espacio verde de uso cotidiano
    y, contadas, pesarían igual que un parque.
    """
    df = _csv('espacios_verdes')
    if solo_utilizables:
        df = df[df['clasificac'].isin(CLASES_VERDE_UTILIZABLE)]
    vertices = [geo.parsear_wkt_vertices(w) for w in df['geometry']]
    centro = np.array([v.mean(axis=0) if len(v) else [np.nan, np.nan] for v in vertices])
    out = _puntos('espacios_verdes', df['nombre'], df['clasificac'], centro[:, 1], centro[:, 0],
                  area_m2=pd.to_numeric(df['area'], errors='coerce').to_numpy())
    out['_vertices'] = vertices
    return out


def vertices_espacios_verdes(verdes):
    """Todos los vértices de los polígonos, para medir distancia al borde y no al centroide."""
    v = np.vstack([x for x in verdes['_vertices'] if len(x)])
    return v[:, 1], v[:, 0]


CARGADORES_PUNTOS = {
    'subte': cargar_subte,
    'tren': cargar_tren,
    'metrobus': cargar_metrobus,
    'hospitales': cargar_hospitales,
    'educacion': cargar_educacion,
    'culturales': cargar_culturales,
    'gastronomia': cargar_gastronomia,
    'espacios_verdes': cargar_espacios_verdes,
}


def cargar_todas_las_fuentes_puntuales():
    return {nombre: cargador() for nombre, cargador in CARGADORES_PUNTOS.items()}


# ---------------------------------------------------------------------------
# Censo 2022 por comuna
# ---------------------------------------------------------------------------

def _hoja_principal(cuadro):
    xls = pd.ExcelFile(CENSO_RAW_DIR / f'c2022_caba_{cuadro}.xlsx')
    hoja = next(s for s in xls.sheet_names if re.fullmatch(r'Cuadro\s*\d+\.\d+', s.replace('\xa0', ' ')))
    return pd.read_excel(xls, sheet_name=hoja, header=None), xls


def _filas_comuna(df):
    """Filas de las 15 comunas, identificadas por el código INDEC (02007 ... 02105 = comuna 1 ... 15)."""
    codigo = df[0].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(5)
    mask = codigo.str.fullmatch(r'02\d{3}') & (codigo != '02000')
    out = df[mask].copy()
    out.index = (codigo[mask].str[2:].astype(int) // 7).rename('comuna')
    return out


def cargar_censo_comunas():
    """Tabla de 15 comunas con las variables del Censo 2022 usadas en el proyecto.

    Las posiciones de columna corresponden a la estructura publicada por INDEC
    (resultados definitivos CABA, noviembre 2023) y se validan con asserts de totales.
    """
    c2, _ = _hoja_principal('est_c2_1')
    c2 = _filas_comuna(c2)
    censo = pd.DataFrame({
        'superficie_km2': c2[2], 'poblacion_total': c2[3], 'densidad_hab_km2': c2[4],
    })

    # Población en viviendas particulares: una hoja por comuna (Cuadro 3.1.1 ... 3.1.15).
    _, xls = _hoja_principal('est_c3_1')
    pob_part = {}
    for hoja in xls.sheet_names:
        m = re.fullmatch(r'Cuadro\s*3\.1\.(\d+)', hoja.replace('\xa0', ' '))
        if m:
            d = pd.read_excel(xls, sheet_name=hoja, header=None)
            fila_total = d[d[0].astype(str).str.strip() == 'Total'].iloc[0]
            pob_part[int(m.group(1))] = fila_total[2]
    censo['poblacion_viv_particulares'] = pd.Series(pob_part)

    v1 = _filas_comuna(_hoja_principal('vivienda_c1_1')[0])
    censo['viviendas_total'] = v1[2]
    censo['viviendas_particulares'] = v1[3]
    censo['viviendas_ocupadas'] = v1[4]
    censo['viviendas_uso_temporal'] = v1[5]          # se usa para vacaciones, fin de semana u otro uso temporal
    censo['viviendas_uso_oficina'] = v1[6]           # se usa como oficina, consultorio, comercio
    censo['viviendas_en_alquiler_o_venta'] = v1[7]   # desocupada, en alquiler o venta

    v2 = _filas_comuna(_hoja_principal('vivienda_c2_1')[0])
    censo['hogares'] = v2[3]

    v3 = _filas_comuna(_hoja_principal('vivienda_c3_1')[0])
    censo['viviendas_ocupadas_casa'] = v3[3]
    censo['viviendas_ocupadas_departamento'] = v3[6]

    h6 = _filas_comuna(_hoja_principal('hogares_c6_1')[0])
    censo['hogares_propietarios'] = h6[3]
    censo['hogares_inquilinos'] = h6[8]

    censo = censo.apply(pd.to_numeric, errors='coerce')
    assert len(censo) == 15 and censo.notna().all().all(), 'Censo: faltan comunas o variables'
    assert censo['poblacion_total'].sum() == 3_121_707, 'Censo: la población no suma el total de CABA'
    assert censo['viviendas_total'].sum() == 1_615_300, 'Censo: las viviendas no suman el total de CABA'

    # Indicadores derivados (proporciones sobre el denominador natural de cada variable).
    censo['tamano_medio_hogar'] = censo['poblacion_viv_particulares'] / censo['hogares']
    censo['pct_hogares_inquilinos'] = 100 * censo['hogares_inquilinos'] / censo['hogares']
    censo['pct_viviendas_departamento'] = 100 * censo['viviendas_ocupadas_departamento'] / censo['viviendas_ocupadas']
    censo['pct_viviendas_uso_temporal'] = 100 * censo['viviendas_uso_temporal'] / censo['viviendas_particulares']
    censo['pct_viviendas_en_alquiler_o_venta'] = (100 * censo['viviendas_en_alquiler_o_venta']
                                                  / censo['viviendas_particulares'])
    return censo.reset_index()
