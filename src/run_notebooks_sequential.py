"""Ejecuta y guarda los notebooks numerados en orden, deteniéndose ante el primer error."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
PATTERN = re.compile(r"^\d{2}_.+\.ipynb$")


def main():
    notebooks = sorted(
        (p for p in NOTEBOOKS.glob("*.ipynb") if PATTERN.match(p.name)),
        key=lambda p: p.name
    )
    if not notebooks:
        raise FileNotFoundError(f"No se encontraron notebooks numerados en {NOTEBOOKS}")

    print(f"Se ejecutarán {len(notebooks)} notebooks en orden: "
          f"{notebooks[0].name} → {notebooks[-1].name}", flush=True)
    for number, notebook in enumerate(notebooks, start=1):
        relative = notebook.relative_to(ROOT)
        print(f"\n[{number}/{len(notebooks)}] Ejecutando {relative}", flush=True)
        command = [
            sys.executable, "-m", "jupyter", "nbconvert",
            "--to", "notebook",
            "--execute",
            "--inplace",
            "--ExecutePreprocessor.timeout=-1",
            "--ExecutePreprocessor.allow_errors=False",
            str(relative),
        ]
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode != 0:
            print(f"\nERROR: se detuvo en {relative}. "
                  "Los notebooks anteriores ya quedaron guardados con outputs.", flush=True)
            return result.returncode
        print(f"OK: outputs guardados en {relative}", flush=True)

    print("\nEjecución completa: todos los notebooks terminaron sin errores.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
