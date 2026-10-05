"""Rutas centralizadas del proyecto, relativas a la raíz del repositorio."""

from pathlib import Path


def find_repo_root(start=None):
    """Sube desde `start` (o el directorio actual) hasta encontrar la raíz del repo."""
    start = Path(start or Path.cwd()).resolve()
    for path in [start, *start.parents]:
        if (path / 'data' / 'raw').exists() and (path / 'README.md').exists():
            return path
    raise FileNotFoundError('No se encontró la raíz del repo. Ejecutar dentro del proyecto.')


REPO_ROOT = find_repo_root(Path(__file__).parent)
RAW_DIR = REPO_ROOT / 'data' / 'raw'
EXTERNAS_RAW_DIR = RAW_DIR / 'externas'
CENSO_RAW_DIR = EXTERNAS_RAW_DIR / 'censo_2022'
PROCESSED_DIR = REPO_ROOT / 'data' / 'processed'
REPORTS_DIR = PROCESSED_DIR / 'reports'

BASE_CONSOLIDADA = PROCESSED_DIR / 'df_publicaciones_consolidadas_con_outliers_v1.csv'
CACHE_GEOCODIFICACION = PROCESSED_DIR / 'geocodificacion_usig_cache.csv'
