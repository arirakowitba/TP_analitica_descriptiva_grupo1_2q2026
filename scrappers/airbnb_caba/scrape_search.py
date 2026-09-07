"""
ETAPA 1 — Censo de anuncios de Airbnb en CABA.

El problema y la solución:
Airbnb corta cualquier consulta en 15 páginas x 18 resultados (~270 anuncios).
No hay forma de pedir la 16a. La salida es particionar el territorio: se busca
por bounding box (ne_lat/ne_lng/sw_lat/sw_lng) y, cuando una celda devuelve 15
páginas (= saturada), se la parte en 4 y se repite. Un quadtree adaptativo:
baja mucho en Palermo/Recoleta/Centro y casi nada en el sur.

Criterio de corte: len(paginationInfo.pageCursors) < 15 significa que esa celda
entra completa. Es un dato que Airbnb devuelve, no una estimación nuestra.

Uso:
    python scrape_search.py --checkin 2026-10-15 --checkout 2026-10-20
    python scrape_search.py --max-cells 5        # prueba de humo
    python scrape_search.py                      # reanuda donde quedó
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

from airbnb_common import (
    Blocked,
    HOST,
    jsonl_append,
    jsonl_gz_append,
    jsonl_ids,
    listing_id_from_gid,
    make_cursor,
    new_session,
    polite_sleep,
    get_deferred_state,
)

OUT = Path(__file__).parent
RAW = OUT / "search_raw.jsonl"
QUEUE = OUT / "cells_pending.json"
# nodos crudos comprimidos: mejorar el parser sin re-correr el censo
FULL = OUT / "search_full.jsonl.gz"

# Bounding box de CABA (con un pequeño margen)
CABA = (-34.5265, -58.3350, -34.7050, -58.5310)  # ne_lat, ne_lng, sw_lat, sw_lng

PAGE_SIZE = 18
MAX_PAGES = 15            # tope duro de Airbnb
MIN_CELL_DEG = 0.0015     # ~150 m: piso para no recursar infinito


def build_url(cell, page: int, checkin: str, checkout: str, adults: int) -> str:
    ne_lat, ne_lng, sw_lat, sw_lng = cell
    params = {
        "refinement_paths[]": "/homes",
        "search_by_map": "true",
        "search_type": "user_map_move",
        "ne_lat": ne_lat, "ne_lng": ne_lng,
        "sw_lat": sw_lat, "sw_lng": sw_lng,
        "zoom": 15,
        "adults": adults,
        "checkin": checkin,
        "checkout": checkout,
    }
    if page > 0:
        params["cursor"] = make_cursor(page * PAGE_SIZE)
    return f"{HOST}/s/homes?" + urlencode(params)


def _lines(struct, field):
    return " | ".join(
        m.get("body", "") for m in (struct or {}).get(field, []) or [] if m
    )


# Typenames de precio conocidos. Si Airbnb agrega uno nuevo con otras claves,
# el precio de esos anuncios volvería a salir null EN SILENCIO: ya pasó una vez
# y costó el 32% de la serie corta (y habría costado el 92% de la mensual, donde
# casi todo aplica descuento). Por eso el parser cuenta lo que no pudo leer y lo
# grita al final de la corrida, en vez de dejarlo pasar.
PRECIO_CONOCIDOS = {"QualifiedDisplayPriceLine", "DiscountedDisplayPriceLine"}
AVISOS: dict[str, int] = {}


def _avisar(msg: str) -> None:
    AVISOS[msg] = AVISOS.get(msg, 0) + 1


def _desglose_precio(sdp):
    """`structuredDisplayPrice.explanationData` traía dos cosas que se perdían:

    - el precio unitario CON centavos ("5 noches por $ 36,00 USD"). Hasta ahora
      el precio por noche se calculaba dividiendo el total ya redondeado, que
      arrastra error.
    - un aviso de baja reciente de precio ("Hace poco, X bajó el precio para
      estas fechas, con respecto a la tarifa promedio de las últimas 60
      noches"), que es una señal de presión competitiva por anuncio.
    """
    ed = (sdp or {}).get("explanationData") or {}
    unitario = total = aviso = None
    for grupo in ed.get("priceDetails") or []:
        if grupo.get("content"):
            aviso = grupo["content"]
        for it in grupo.get("items") or []:
            if unitario is None:
                unitario = it.get("description")
            if total is None:
                total = it.get("priceString")
    return unitario, total, aviso


def parse_result(node: dict, cell, checkin: str = None, checkout: str = None) -> dict | None:
    dsl = node.get("demandStayListing") or {}
    lid = listing_id_from_gid(dsl.get("id", "")) if dsl.get("id") else None
    if not lid:
        return None
    coord = (dsl.get("location") or {}).get("coordinate") or {}
    price = (node.get("structuredDisplayPrice") or {}).get("primaryLine") or {}
    price2 = (node.get("structuredDisplayPrice") or {}).get("secondaryLine") or {}
    desglose, total_exacto, aviso = _desglose_precio(node.get("structuredDisplayPrice"))

    # guarda contra la falla que ya nos pasó: un typename nuevo con otras claves
    precio_txt = price.get("price") or price.get("discountedPrice")
    tn = price.get("__typename")
    if tn and tn not in PRECIO_CONOCIDOS:
        _avisar(f"typename de precio DESCONOCIDO: {tn} claves={sorted(price)}")
    if price and not precio_txt:
        _avisar(f"precio NO leido en {tn} claves={sorted(price)}")
    sc = node.get("structuredContent") or {}
    pics = node.get("contextualPictures") or []
    lpo = node.get("listingParamOverrides") or {}
    title = node.get("title") or ""
    # OJO (verificado 2026-09-05): en modo mapa (search_by_map=true, el único que
    # acepta bounding box) Airbnb devuelve title=null y subtitle=null. Y en modo
    # lista el title pasó a ser "Departamento en Buenos Aires": la ciudad, no el
    # barrio. O sea: el barrio ya NO viene en los resultados de búsqueda.
    # El tipo de propiedad sale de la etapa 2 (room_type / tipo_propiedad).
    tipo, _, barrio = title.partition(" en ")
    return {
        "listing_id": lid,
        "url": f"{HOST}/rooms/{lid}",
        "nombre": ((dsl.get("description") or {}).get("name") or {})
                  .get("localizedStringWithTranslationPreference"),
        "titulo_card": title,
        "tipo_habitacion_txt": tipo or None,
        "barrio_card": barrio or None,
        "latitud": coord.get("latitude"),
        "longitud": coord.get("longitude"),
        "rating_txt": node.get("avgRatingLocalized"),
        "rating_a11y": node.get("avgRatingA11yLabel"),
        "badges": " | ".join(b.get("text", "") for b in node.get("badges") or []),
        "linea_primaria": _lines(sc, "primaryLine"),
        "linea_secundaria": _lines(sc, "secondaryLine"),
        # primaryLine viene con dos typenames distintos y claves distintas:
        #   QualifiedDisplayPriceLine  -> price
        #   DiscountedDisplayPriceLine -> discountedPrice + originalPrice
        # (~45% de los anuncios son del segundo tipo; leer sólo "price" perdía
        # el precio de casi la mitad del censo)
        "precio_tipo": price.get("__typename"),
        "precio_txt": precio_txt,
        "precio_original_txt": price.get("originalPrice"),
        "precio_qualifier": price.get("qualifier"),
        "precio_a11y": price.get("accessibilityLabel"),
        "precio_secundario": price2.get("price") if isinstance(price2, dict) else None,
        "precio_desglose_txt": desglose,
        "precio_total_exacto_txt": total_exacto,
        "precio_aviso": aviso,
        "cantidad_fotos": len(pics),
        "foto_principal": (pics[0] or {}).get("picture") if pics else None,
        # listingParamOverrides vuelve null: caemos a la ventana de la consulta,
        # que es la que determinó el precio de arriba
        "checkin_consulta": lpo.get("checkin") or checkin,
        "checkout_consulta": lpo.get("checkout") or checkout,
        "celda": ",".join(f"{c:.5f}" for c in cell),
    }


def fetch_page(session, cell, page, args):
    url = build_url(cell, page, args.checkin, args.checkout, args.adults)
    j = get_deferred_state(session, url)
    p = j["niobeClientData"][0][1]["data"]["presentation"]["staysSearch"]
    res = p["results"]
    nodes = list(res.get("searchResults") or [])
    # los resultados del mapa suelen traer anuncios que no entran en la lista
    map_nodes = ((p.get("mapResults") or {}).get("mapSearchResults")) or []
    nodes += list(map_nodes)
    n_pages = len((res.get("paginationInfo") or {}).get("pageCursors") or [])
    return nodes, n_pages


def split(cell):
    ne_lat, ne_lng, sw_lat, sw_lng = cell
    mid_lat = (ne_lat + sw_lat) / 2
    mid_lng = (ne_lng + sw_lng) / 2
    return [
        (ne_lat, ne_lng, mid_lat, mid_lng),
        (ne_lat, mid_lng, mid_lat, sw_lng),
        (mid_lat, ne_lng, sw_lat, mid_lng),
        (mid_lat, mid_lng, sw_lat, sw_lng),
    ]


def too_small(cell) -> bool:
    ne_lat, ne_lng, sw_lat, sw_lng = cell
    return abs(ne_lat - sw_lat) < MIN_CELL_DEG or abs(ne_lng - sw_lng) < MIN_CELL_DEG


def main():
    ap = argparse.ArgumentParser()
    hoy = date.today()
    ap.add_argument("--checkin", default=str(hoy + timedelta(days=45)))
    ap.add_argument("--checkout", default=str(hoy + timedelta(days=50)))
    ap.add_argument("--adults", type=int, default=2)
    ap.add_argument("--max-cells", type=int, default=0, help="0 = sin límite")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--sin-crudo", action="store_true",
                    help="no guardar los nodos crudos")
    ap.add_argument("--sufijo", default="",
                    help="sufijo de los archivos de salida. Sirve para correr "
                         "una serie con OTRA ventana de fechas sin mezclarla "
                         "con la anterior: --sufijo _mensual escribe en "
                         "search_raw_mensual.jsonl y cells_pending_mensual.json")
    args = ap.parse_args()

    global RAW, QUEUE, FULL
    if args.sufijo:
        RAW = OUT / f"search_raw{args.sufijo}.jsonl"
        QUEUE = OUT / f"cells_pending{args.sufijo}.json"
        FULL = OUT / f"search_full{args.sufijo}.jsonl.gz"
        print(f"Serie aparte: escribo en {RAW.name} / {QUEUE.name}")

    if args.reset:
        for f in (RAW, QUEUE):
            f.unlink(missing_ok=True)

    seen = jsonl_ids(RAW)
    pending = json.loads(QUEUE.read_text()) if QUEUE.exists() else [list(CABA)]
    print(f"Reanudando: {len(seen)} anuncios ya guardados, {len(pending)} celdas en cola")
    print(f"Ventana de fechas: {args.checkin} -> {args.checkout} ({args.adults} huéspedes)")

    session = new_session()
    procesadas = 0

    try:
        while pending:
            cell = tuple(pending.pop(0))
            try:
                nodes, n_pages = fetch_page(session, cell, 0, args)
            except Blocked as e:
                print(f"  BLOQUEADO en {cell}: {e}\n  -> devuelvo la celda a la cola y corto.")
                pending.insert(0, list(cell))
                break

            nuevos = 0
            for nd in nodes:
                rec = parse_result(nd, cell, args.checkin, args.checkout)
                if rec and rec["listing_id"] not in seen:
                    seen.add(rec["listing_id"])
                    if not args.sin_crudo:
                        jsonl_gz_append(FULL, {"listing_id": rec["listing_id"],
                                               "celda": rec["celda"], "nodo": nd})
                    jsonl_append(RAW, rec)
                    nuevos += 1

            saturada = n_pages >= MAX_PAGES
            if saturada and not too_small(cell):
                pending.extend(split(cell))
                estado = "SATURADA -> parto en 4"
            else:
                # celda entra completa: recorro el resto de las páginas
                for page in range(1, n_pages):
                    polite_sleep()
                    try:
                        nodes, _ = fetch_page(session, cell, page, args)
                    except Blocked as e:
                        print(f"  BLOQUEADO paginando {cell} p{page}: {e}")
                        break
                    for nd in nodes:
                        rec = parse_result(nd, cell, args.checkin, args.checkout)
                        if rec and rec["listing_id"] not in seen:
                            seen.add(rec["listing_id"])
                            if not args.sin_crudo:
                                jsonl_gz_append(FULL, {"listing_id": rec["listing_id"],
                                                       "celda": rec["celda"], "nodo": nd})
                            jsonl_append(RAW, rec)
                            nuevos += 1
                estado = "completa"

            procesadas += 1
            print(f"[{procesadas}] {cell} paginas={n_pages} {estado} "
                  f"+{nuevos} nuevos | total={len(seen)} | cola={len(pending)}")
            QUEUE.write_text(json.dumps(pending))
            polite_sleep()

            if args.max_cells and procesadas >= args.max_cells:
                print("Límite de celdas alcanzado (prueba de humo).")
                break
    except KeyboardInterrupt:
        print("\nInterrumpido. El progreso quedó guardado, volvé a correr para reanudar.")

    QUEUE.write_text(json.dumps(pending))
    if AVISOS:
        print("!" * 70)
        print("ATENCION: el parser encontro estructuras que no sabe leer.")
        print("Puede ser que Airbnb haya cambiado el formato del precio.")
        for msg, n in sorted(AVISOS.items(), key=lambda x: -x[1]):
            print(f"  [{n} veces] {msg}")
        print("Los anuncios afectados quedaron SIN precio. Revisalo antes de")
        print("usar el dataset. El crudo esta en search_full*.jsonl.gz, asi que")
        print("se arregla con reparse.py y NO hay que re-scrapear.")
        print("!" * 70)
    print(f"\nListo. {len(seen)} anuncios únicos en {RAW.name}. Cola pendiente: {len(pending)} celdas.")
    if not pending:
        print("Censo COMPLETO. Corré:  python export_csv.py")


if __name__ == "__main__":
    sys.exit(main())
