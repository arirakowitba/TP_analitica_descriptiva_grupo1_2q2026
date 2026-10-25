"""Ejecuta y guarda notebooks numerados en orden, deteniéndose ante el primer error."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
PATTERN = re.compile(r"^\d{2}_.+\.ipynb$")


def add_missing_cell_ids(notebook):
    """Añade IDs estables requeridos por nbformat sin alterar el contenido analítico."""
    data = json.loads(notebook.read_text(encoding="utf-8"))
    used = {cell.get("id") for cell in data.get("cells", []) if cell.get("id")}
    for index, cell in enumerate(data.get("cells", []), start=1):
        if cell.get("id"):
            continue
        candidate = f"pe3-cell-{index}"
        suffix = 1
        while candidate in used:
            candidate = f"pe3-cell-{index}-{suffix}"
            suffix += 1
        cell["id"] = candidate
        used.add(candidate)
    notebook.write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )


def main():
    notebooks = sorted(
        (p for p in NOTEBOOKS.glob("*.ipynb") if PATTERN.match(p.name)),
        key=lambda p: p.name
    )
    if not notebooks:
        raise FileNotFoundError(f"No se encontraron notebooks numerados en {NOTEBOOKS}")

    print(f"Se ejecutarán {len(notebooks)} notebooks en orden: "
          f"{notebooks[0].name} → {notebooks[-1].name}", flush=True)

    with tempfile.TemporaryDirectory(prefix="jupyter-pe3-config-") as config_dir:
        # Cifrar el tráfico local del kernel para no degradar la validación
        # ni emitir el aviso de IPKernelApp sobre sockets TCP sin cifrado.
        (Path(config_dir) / "jupyter_config.py").write_text(
            "c = get_config()\nc.KernelManager.transport_encryption = 'auto'\n",
            encoding="utf-8",
        )

        for number, notebook in enumerate(notebooks, start=1):
            relative = notebook.relative_to(ROOT)
            print(f"\n[{number}/{len(notebooks)}] Ejecutando {relative}", flush=True)
            add_missing_cell_ids(notebook)
            command = [
                sys.executable, "-m", "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                "--inplace",
                "--ExecutePreprocessor.timeout=-1",
                "--ExecutePreprocessor.allow_errors=False",
                str(relative),
            ]
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(ROOT) + (
                os.pathsep + existing_pythonpath if existing_pythonpath else ""
            )
            env["JUPYTER_CONFIG_DIR"] = config_dir
            result = subprocess.run(command, cwd=ROOT, env=env, check=False)
            if result.returncode != 0:
                print(f"\nERROR: se detuvo en {relative}. "
                      "Los notebooks anteriores ya quedaron guardados con outputs.", flush=True)
                return result.returncode
            print(f"OK: outputs guardados en {relative}", flush=True)

    print("\nEjecución completa: todos los notebooks terminaron sin errores.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
