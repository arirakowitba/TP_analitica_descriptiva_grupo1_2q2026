"""Extraccion segmentada de alquileres de Mercado Libre Inmuebles (CABA).

Este orquestador evita el limite practico de unas 2.000 publicaciones por
busqueda recorriendo cada barrio por separado. Reutiliza el parser robusto del
TP y consolida los segmentos en un CSV por operacion, deduplicado por item_id.

Requisito: colocar este archivo junto a
``scraper_mercadolibre_inmuebles_modificado.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# Admite guardarlo tanto en la raiz del repo como dentro de /scrappers.
HERE = Path(__file__).resolve().parent
for candidate in (HERE, HERE / "scrappers"):
    if (candidate / "scraper_mercadolibre_inmuebles_modificado.py").exists():
        sys.path.insert(0, str(candidate))
        break

try:
    from scraper_mercadolibre_inmuebles_modificado import Config, FIELDS, run
except ImportError as exc:
    raise SystemExit(
        "No se encontro scraper_mercadolibre_inmuebles_modificado.py. "
        "Coloca el orquestador en la raiz del repo o dentro de /scrappers."
    ) from exc


OPERATIONS = {
    "normal": "alquiler",
    "temporal": "alquiler-temporal",
}

# Barrios oficiales de CABA. Si Mercado Libre no reconoce alguno, ese segmento
# simplemente terminara sin tarjetas y quedara registrado en el resumen.
CABA_BARRIOS = [
    "agronomia", "almagro", "balvanera", "barracas", "belgrano", "boedo",
    "caballito", "chacarita", "coghlan", "colegiales", "constitucion",
    "flores", "floresta", "la-boca", "la-paternal", "liniers", "mataderos",
    "monserrat", "monte-castro", "nueva-pompeya", "nunez", "palermo",
    "parque-avellaneda", "parque-chacabuco", "parque-chas",
    "parque-patricios", "puerto-madero", "recoleta", "retiro", "saavedra",
    "san-cristobal", "san-nicolas", "san-telmo", "velez-sarsfield",
    "versalles", "villa-crespo", "villa-del-parque", "villa-devoto",
    "villa-general-mitre", "villa-lugano", "villa-luro", "villa-ortuzar",
    "villa-pueyrredon", "villa-real", "villa-riachuelo", "villa-santa-rita",
    "villa-soldati", "villa-urquiza",
]


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not value:
        raise argparse.ArgumentTypeError("El barrio no puede quedar vacio")
    return value


def positive(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Debe ser mayor que cero")
    return parsed


def search_url(operation_slug: str, barrio: str) -> str:
    return (
        "https://inmuebles.mercadolibre.com.ar/departamentos/"
        f"{operation_slug}/capital-federal/{barrio}/"
    )


def read_rows(csv_path: Path):
    if not csv_path.exists():
        return
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def consolidate(operation_dir: Path) -> tuple[Path, int, int]:
    """Une segmentos y conserva una fila por item_id.

    Si una publicacion aparece en mas de un barrio, se conserva la version con
    mayor completitud_pct. En empate, queda la primera encontrada.
    """
    selected: dict[str, dict[str, str]] = {}
    rows_seen = 0

    for csv_path in sorted(operation_dir.glob("segmentos/*/propiedades_mercadolibre.csv")):
        for row in read_rows(csv_path):
            rows_seen += 1
            item_id = (row.get("item_id") or "").strip()
            if not item_id:
                continue
            try:
                quality = float(row.get("completitud_pct") or 0)
                previous_quality = float(
                    selected.get(item_id, {}).get("completitud_pct") or -1
                )
            except ValueError:
                quality, previous_quality = 0, -1
            if item_id not in selected or quality > previous_quality:
                selected[item_id] = row

    output = operation_dir / "propiedades_mercadolibre_consolidado.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selected.values())
    temporary.replace(output)
    return output, rows_seen, len(selected)


def execute(args: argparse.Namespace) -> None:
    operations = list(OPERATIONS) if args.operacion == "ambos" else [args.operacion]
    barrios = CABA_BARRIOS
    if args.barrios:
        barrios = list(dict.fromkeys(slugify(x) for x in args.barrios.split(",") if x.strip()))

    summary: dict[str, object] = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "operations": {},
    }

    for operation in operations:
        operation_slug = OPERATIONS[operation]
        operation_dir = args.output_dir / operation
        segments_dir = operation_dir / "segmentos"
        print(f"\n=== {operation.upper()}: {len(barrios)} barrios ===")

        completed = 0
        failures: list[dict[str, str]] = []
        for index, barrio in enumerate(barrios, start=1):
            print(f"\n[{index}/{len(barrios)}] {operation} - {barrio}")
            segment_dir = segments_dir / barrio
            try:
                run(Config(
                    search_url=search_url(operation_slug, barrio),
                    output_dir=segment_dir,
                    page_start=1,
                    max_pages=args.max_pages,
                    max_properties=args.max_properties_per_barrio,
                    checkpoint_every=args.checkpoint_every,
                    min_delay=args.min_delay,
                    max_delay=args.max_delay,
                    timeout=args.timeout,
                    retries=args.retries,
                ))
                completed += 1
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:  # El resto de los barrios debe continuar.
                failures.append({"barrio": barrio, "error": repr(exc)})
                print(f"ERROR en {barrio}: {exc!r}", file=sys.stderr)

            # Consolidacion incremental: deja un maestro util aunque se corte.
            output, rows_seen, unique_rows = consolidate(operation_dir)
            print(f"Maestro parcial: {unique_rows} unicos ({rows_seen} filas leidas)")

        output, rows_seen, unique_rows = consolidate(operation_dir)
        summary["operations"][operation] = {
            "segments_completed": completed,
            "segments_requested": len(barrios),
            "failures": failures,
            "rows_before_deduplication": rows_seen,
            "unique_properties": unique_rows,
            "output_csv": str(output),
        }

    summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary_path = args.output_dir / "resumen_extraccion.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nResumen guardado en {summary_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extrae alquiler normal y temporal de Mercado Libre por barrio"
    )
    parser.add_argument(
        "--operacion", choices=["normal", "temporal", "ambos"], default="ambos"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/raw/mercadolibre_alquileres")
    )
    parser.add_argument(
        "--barrios",
        help="Lista separada por comas. Si se omite, recorre los 48 barrios de CABA.",
    )
    parser.add_argument("--max-pages", type=positive)
    parser.add_argument("--max-properties-per-barrio", type=positive)
    parser.add_argument("--checkpoint-every", type=positive, default=150)
    parser.add_argument("--min-delay", type=float, default=8.0)
    parser.add_argument("--max-delay", type=float, default=12.0)
    parser.add_argument("--timeout", type=positive, default=30)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    if args.min_delay < 0 or args.max_delay < args.min_delay or args.retries < 0:
        parser.error("Revisa min-delay, max-delay y retries")
    execute(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
