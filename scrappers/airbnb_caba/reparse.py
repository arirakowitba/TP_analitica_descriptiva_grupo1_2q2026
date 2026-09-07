"""
Re-parsea desde las respuestas CRUDAS guardadas. No toca la red.

¿Para qué? Los .jsonl guardan el registro ya parseado, así que cada campo que
descubrimos tarde exigía volver a scrapear. Con `pdp_full*.jsonl.gz` y
`search_full*.jsonl.gz` en disco, mejorar el parser es correr esto: minutos en
vez de horas, y sin gastar un request contra Airbnb.

Uso:
    python reparse.py                    # re-parsea la serie base
    python reparse.py --sufijo _mensual  # la serie mensual
    python reparse.py --que pdp          # sólo las fichas
    python reparse.py --que search       # sólo el censo

Reescribe pdp_raw*.jsonl, amenities_raw*.jsonl y search_raw*.jsonl. Los deja
con .bak antes de tocarlos: si el parser nuevo sale peor, se vuelve atrás.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from airbnb_common import jsonl_append, jsonl_gz_read
import scrape_pdp
import scrape_search

OUT = Path(__file__).parent


def respaldar(p: Path) -> None:
    if p.exists():
        shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
        print(f"  respaldo: {p.name} -> {p.name}.bak")


def reparse_pdp(suf: str) -> int:
    full = OUT / f"pdp_full{suf}.jsonl.gz"
    if not full.exists():
        print(f"No hay {full.name}. Las fichas viejas se bajaron antes de que "
              f"existiera el guardado de crudo, así que no se pueden re-parsear.")
        return 0
    destino = OUT / f"pdp_raw{suf}.jsonl"
    amen_dst = OUT / f"amenities_raw{suf}.jsonl"
    respaldar(destino); respaldar(amen_dst)
    destino.unlink(missing_ok=True); amen_dst.unlink(missing_ok=True)

    n = fallos = 0
    for reg in jsonl_gz_read(full):
        lid = str(reg.get("listing_id"))
        try:
            rec, amen = scrape_pdp.parse(lid, reg["resp"])
        except Exception as e:
            fallos += 1
            if fallos <= 3:
                print(f"  ERROR parseando {lid}: {type(e).__name__}: {e}")
            continue
        # el scraped_at_utc del crudo, no el de ahora: el dato es de cuando se bajó
        if reg.get("scraped_at_utc"):
            rec["scraped_at_utc"] = reg["scraped_at_utc"]
        jsonl_append(destino, rec)
        for a in amen:
            jsonl_append(amen_dst, a)
        n += 1
        if n % 2000 == 0:
            print(f"  {n} fichas re-parseadas")
    print(f"pdp: {n} fichas re-parseadas, {fallos} fallos -> {destino.name}")
    return n


def reparse_search(suf: str) -> int:
    full = OUT / f"search_full{suf}.jsonl.gz"
    if not full.exists():
        print(f"No hay {full.name}.")
        return 0
    destino = OUT / f"search_raw{suf}.jsonl"
    respaldar(destino)
    destino.unlink(missing_ok=True)

    n = fallos = 0
    for reg in jsonl_gz_read(full):
        celda = tuple(float(x) for x in str(reg.get("celda", "")).split(","))
        try:
            rec = scrape_search.parse_result(reg["nodo"], celda)
        except Exception as e:
            fallos += 1
            if fallos <= 3:
                print(f"  ERROR: {type(e).__name__}: {e}")
            continue
        if rec:
            jsonl_append(destino, rec)
            n += 1
    print(f"search: {n} anuncios re-parseados, {fallos} fallos -> {destino.name}")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sufijo", default="")
    ap.add_argument("--que", choices=["pdp", "search", "todo"], default="todo")
    args = ap.parse_args()
    if args.que in ("search", "todo"):
        reparse_search(args.sufijo)
    if args.que in ("pdp", "todo"):
        reparse_pdp(args.sufijo)
    print("\nListo. Ahora corré:  python export_csv.py"
          + (f" --sufijo {args.sufijo}" if args.sufijo else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
