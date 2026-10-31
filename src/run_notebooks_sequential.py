"""Ejecuta y guarda notebooks numerados en orden, deteniéndose ante el primer error."""
from pathlib import Path
import argparse
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=1, help="Primer número de notebook (incluido).")
    parser.add_argument("--end", type=int, default=99, help="Último número de notebook (incluido).")
    args = parser.parse_args(argv)
    if not 1 <= args.start <= args.end <= 99:
        parser.error("Se requiere 1 <= start <= end <= 99.")
    notebooks = sorted(
        (p for p in NOTEBOOKS.glob("*.ipynb")
         if PATTERN.match(p.name) and args.start <= int(p.name[:2]) <= args.end),
        key=lambda p: p.name
    )
    if not notebooks:
        raise FileNotFoundError(f"No se encontraron notebooks numerados en {NOTEBOOKS}")

    print(f"Se ejecutarán {len(notebooks)} notebooks en orden: "
          f"{notebooks[0].name} -> {notebooks[-1].name}", flush=True)

    with tempfile.TemporaryDirectory(prefix="jupyter-pe3-kernel-") as kernel_dir:
        # Un kernelspec global llamado python3 puede apuntar a otro entorno.
        # El kernel temporal usa exactamente el Python que ejecuta este módulo.
        kernel_name = "tp-analitica-validation"
        spec_dir = Path(kernel_dir) / "kernels" / kernel_name
        spec_dir.mkdir(parents=True)
        (spec_dir / "kernel.json").write_text(json.dumps({
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "TP Analítica (validación)",
            "language": "python",
        }), encoding="utf-8")

        for number, notebook in enumerate(notebooks, start=1):
            relative = notebook.relative_to(ROOT)
            print(f"\n[{number}/{len(notebooks)}] Ejecutando {relative}", flush=True)
            add_missing_cell_ids(notebook)
            command = [
                sys.executable, "-m", "nbconvert",
                "--to", "notebook",
                "--execute",
                "--inplace",
                "--ExecutePreprocessor.timeout=-1",
                "--ExecutePreprocessor.allow_errors=False",
                f"--ExecutePreprocessor.kernel_name={kernel_name}",
                str(relative),
            ]
            env = os.environ.copy()
            existing_jupyter_path = env.get("JUPYTER_PATH")
            env["JUPYTER_PATH"] = kernel_dir + (
                os.pathsep + existing_jupyter_path if existing_jupyter_path else ""
            )
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
