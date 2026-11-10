"""Retira únicamente archivos obsoletos enumerados y justificados en el manifiesto."""
from pathlib import Path
import argparse
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Eliminar los archivos enumerados')
    args = parser.parse_args()
    directory = (ROOT / 'data/processed').resolve()
    entries = json.loads((ROOT / 'docs/processed_retirados.json').read_text(encoding='utf-8'))
    candidates = []
    for entry in entries:
        path = (directory / entry['archivo']).resolve()
        if not path.is_relative_to(directory) or path.suffix not in {'.csv', '.png'}:
            raise ValueError(f'Ruta fuera del conjunto permitido: {path}')
        if path.is_file():
            candidates.append(path)
    total = sum(path.stat().st_size for path in candidates)
    print(f'{len(candidates)} archivos obsoletos presentes; {total} bytes')
    if args.apply:
        for path in candidates:
            path.unlink()
        print('Retirados; las exportaciones obsoletas también se eliminaron de los notebooks.')


if __name__ == '__main__':
    main()
