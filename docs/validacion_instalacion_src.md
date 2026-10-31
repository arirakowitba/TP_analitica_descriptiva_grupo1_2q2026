# Instalación del paquete local y validación

Revisión del 31/10/2026 sobre el commit base `2cf13d2`.

## Fallo reproducido

Al ejecutar la primera celda de código del notebook 09 desde `notebooks/`,
`from src import config` producía `ModuleNotFoundError: No module named 'src'`.
Los notebooks 06–08 insertaban la raíz en `sys.path`, pero 09–13 no lo hacían.
El ejecutor ocultaba esa diferencia al agregar `PYTHONPATH`.

Antes de la corrección, `python -m pip install -e .` también fallaba:
el repositorio no contenía `setup.py` ni `pyproject.toml`.

## Corrección

- `pyproject.toml` declara la distribución `tp-analitica-descriptiva-grupo1`,
  sus dependencias y el paquete importable existente `src`. La selección
  explícita de paquetes excluye datos, notebooks y scrapers del descubrimiento.
- `requirements.txt` instala `-e .` desde la raíz. No se descarga un paquete
  externo llamado `src`; se instala el código de este checkout.
- Los notebooks 06–08 usan las mismas importaciones normales que PE3.
- El ejecutor deja de inyectar `PYTHONPATH`, invoca `nbconvert` como módulo del
  intérprete actual y crea un kernelspec temporal con ese mismo intérprete.
  Esto evita seleccionar por accidente un Jupyter o un kernel global.
- La documentación explica instalación, selección de kernel y ejecución por
  tramos. CI comprueba importaciones antes de ejecutar la secuencia.

## Repetir las comprobaciones

Desde la raíz, con Python 3.12 y el entorno virtual activado:

```bash
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -s tests -v
python -m src.run_notebooks_sequential
```

Las dos pruebas de regresión importan los módulos reutilizables desde
`notebooks/` y desde una carpeta temporal externa. Usan `python -I`, eliminan
`PYTHONPATH` y comprueban que `src.config` resuelva este checkout.

La instalación se comprobó en un entorno virtual nuevo, sin acceso a los paquetes
globales, con Python 3.12.7 en Windows. `pip check` no encontró dependencias
incompatibles y las dos pruebas de importación pasaron. El entorno resolvió,
entre otras, NumPy 2.5.4, pandas 3.1.0, SciPy 1.18.1, scikit-learn 1.9.1,
statsmodels 0.15.0, Matplotlib 3.11.2 y nbconvert 7.17.2. No se cambiaron las
versiones del Python global.

La secuencia 01–15 terminó con código de salida 0: **15 notebooks, 187 celdas
de código ejecutadas, 0 outputs de error**. La revisión posterior comprobó que
todas las celdas no vacías tuvieran contador de ejecución y que ninguna salida
fuera de tipo `error`. El notebook 09 se ejecutó completo con la importación
`from src import config`, sin agregar rutas manualmente.

Jupyter emitió avisos de infraestructura sobre el event loop de Windows y el
transporte local del kernel; no detuvieron la ejecución. Las fuentes crudas no
cambiaron. Los notebooks ejecutados y el registro completo se conservaron como
artefactos de validación; el cambio de instalación conserva los outputs
versionados y no incorpora las regeneraciones de CSV ni de imágenes.

Para comprobar solo la continuación de PE3 con insumos previos disponibles:

```bash
python -m src.run_notebooks_sequential --start 9 --end 15
```

La instalación editable requiere conservar el checkout y sus datos. Si se mueve
el repositorio, volver a instalarlo; si cambia el entorno de Jupyter, seleccionar
el kernel correspondiente. No se incluyeron datos dentro de una distribución wheel.
