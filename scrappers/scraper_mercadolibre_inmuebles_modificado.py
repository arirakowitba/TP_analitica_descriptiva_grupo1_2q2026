"""Scraper responsable de tarjetas públicas de Mercado Libre Inmuebles.

No usa credenciales ni abre las fichas individuales. Guarda cada tarjeta en un
journal JSONL y consolida un CSV cada N registros para poder reanudar.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from lxml import html


# =============================================================================
# 1. CONFIGURACIÓN
# =============================================================================

DEFAULT_URL = "https://inmuebles.mercadolibre.com.ar/departamentos/venta/capital-federal/"  # venta por defecto
DEFAULT_OUTPUT = Path("data/raw/mercadolibre_inmuebles")
PAGE_SIZE = 48
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}

FIELDS = [
    "item_id", "fuente", "url", "search_url", "pagina_origen",
    "scraped_at_utc", "titulo", "tipo_propiedad", "tipo_operacion",
    "moneda", "precio", "precio_texto", "desde", "inmobiliaria",
    "direccion", "barrio", "localidad", "provincia",
    "ambientes_min", "ambientes_max", "banios_min", "banios_max",
    "dormitorios_min", "dormitorios_max", "superficie_min_m2",
    "superficie_max_m2", "tipo_superficie", "imagen_principal",
    "destacado", "emprendimiento", "posesion", "unidades_disponibles",
    "atributos_texto", "texto_tarjeta", "parse_warnings",
    # Variables ampliadas y derivadas (también recuperables para filas viejas)
    "posicion_pagina", "slug", "calle", "altura", "comuna",
    "precio_anterior", "descuento_pct", "precio_m2_min", "precio_m2_max",
    "amplitud_superficie_m2", "es_rango_superficie", "es_rango_ambientes",
    "monoambiente", "apto_credito", "balcon", "terraza", "pileta",
    "parrilla", "cochera_mencionada", "amenities_mencionadas",
    "estado_entrega", "cantidad_atributos", "completitud_pct",
    "imagen_id", "imagen_extension",
]


@dataclass(frozen=True)
class Config:
    search_url: str
    output_dir: Path
    page_start: int = 1
    max_pages: int | None = None
    max_properties: int | None = None
    checkpoint_every: int = 150
    min_delay: float = 8.0
    max_delay: float = 12.0
    timeout: int = 30
    retries: int = 2


# =============================================================================
# 2. FUNCIONES DE LIMPIEZA
# =============================================================================

def text_of(node: Any) -> str | None:
    if node is None:
        return None
    value = " ".join(" ".join(node.itertext()).split())
    return value or None


def first_text(node: Any, class_name: str) -> str | None:
    found = node.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), $wanted)]",
        wanted=f" {class_name} ",
    )
    return text_of(found[0]) if found else None


def parse_arg_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"[0-9][0-9.,]*", value)
    if not match:
        return None
    raw = match.group(0)
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1 or ("." in raw and len(raw.rsplit(".", 1)[1]) == 3):
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def number_range(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    nums = re.findall(r"[0-9][0-9.,]*", value)
    parsed = [parse_arg_number(x) for x in nums]
    parsed = [x for x in parsed if x is not None]
    if not parsed:
        return None, None
    return parsed[0], parsed[1] if len(parsed) > 1 else parsed[0]


def integer_range(value: str | None) -> tuple[int | None, int | None]:
    low, high = number_range(value)
    return (int(low) if low is not None else None,
            int(high) if high is not None else None)


def money(value: str | None) -> tuple[str | None, float | None]:
    if not value:
        return None, None
    currency = "USD" if re.search(r"US\$|U\$S|USD", value, re.I) else "ARS"
    return currency, parse_arg_number(value)


def clean_item_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def make_page_url(search_url: str, page: int) -> str:
    base = re.sub(r"/_Desde_\d+_NoIndex_True/?$", "/", search_url.rstrip("/"))
    if page <= 1:
        return base + "/"
    offset = 1 + (page - 1) * PAGE_SIZE
    return f"{base}/_Desde_{offset}_NoIndex_True"


BARRIO_COMUNA = {
    "agronomia": 15, "almagro": 5, "balvanera": 3, "barracas": 4,
    "belgrano": 13, "boedo": 5, "caballito": 6, "chacarita": 15,
    "coghlan": 12, "colegiales": 13, "constitucion": 1, "flores": 7,
    "floresta": 10, "la boca": 4, "la paternal": 15, "liniers": 9,
    "mataderos": 9, "monserrat": 1, "monte castro": 10,
    "nueva pompeya": 4, "nunez": 13, "palermo": 14,
    "parque avellaneda": 9, "parque chacabuco": 7, "parque chas": 15,
    "parque patricios": 4, "puerto madero": 1, "recoleta": 2,
    "retiro": 1, "saavedra": 12, "san cristobal": 3, "san nicolas": 1,
    "san telmo": 1, "velez sarsfield": 10, "versalles": 10,
    "villa crespo": 15, "villa del parque": 11, "villa devoto": 11,
    "villa general mitre": 11, "villa lugano": 8, "villa luro": 10,
    "villa ortuzar": 15, "villa pueyrredon": 12, "villa real": 10,
    "villa riachuelo": 8, "villa santa rita": 11, "villa soldati": 8,
    "villa urquiza": 12,
}


def normalized(value: str | None) -> str:
    import unicodedata
    raw = unicodedata.normalize("NFKD", (value or "").lower())
    return "".join(c for c in raw if not unicodedata.combining(c))


def enrich_row(row: dict[str, Any], position: int | None = None) -> dict[str, Any]:
    """Agrega variables derivadas; funciona también sobre filas ya guardadas."""
    text = normalized(" ".join(str(row.get(k) or "") for k in
                      ("titulo", "texto_tarjeta", "atributos_texto")))
    address = row.get("direccion") or ""
    first_part = address.split(",", 1)[0].strip()
    street_match = re.match(r"^(.*?)(?:\s+(\d{1,6}))?$", first_part)
    barrio_key = normalized(row.get("barrio"))
    comuna = next((v for k, v in BARRIO_COMUNA.items()
                   if k == barrio_key or k in barrio_key), None)
    image = row.get("imagen_principal") or ""
    image_name = image.rsplit("/", 1)[-1].split("?", 1)[0]
    image_id_match = re.search(r"(D_NQ[^.]+|[0-9]+-MLA[0-9_]+)", image_name)
    ext_match = re.search(r"\.([A-Za-z0-9]+)$", image_name)
    smin, smax = row.get("superficie_min_m2"), row.get("superficie_max_m2")
    price = row.get("precio")
    previous_match = re.search(r"(?:antes|precio anterior)\s*(?:us\$|u\$s|\$)?\s*([0-9][0-9.,]*)", text)
    previous = parse_arg_number(previous_match.group(1)) if previous_match else None
    delivery = None
    for label, terms in {
        "entrega_inmediata": ("entrega inmediata", "posesion inmediata"),
        "proxima_entrega": ("proxima entrega", "pronta entrega"),
        "en_construccion": ("en construccion",),
        "en_pozo": ("en pozo", "venta en pozo", "venta en blanco"),
    }.items():
        if any(term in text for term in terms):
            delivery = label
            break
    important = ("precio", "barrio", "ambientes_min", "banios_min",
                 "superficie_min_m2", "inmobiliaria", "imagen_principal")
    row.update({
        "posicion_pagina": position if position is not None else row.get("posicion_pagina"),
        "slug": urlsplit(row.get("url") or "").path.rsplit("/", 1)[-1] or None,
        "calle": street_match.group(1).strip() if street_match else first_part or None,
        "altura": int(street_match.group(2)) if street_match and street_match.group(2) else None,
        "comuna": comuna, "precio_anterior": previous,
        "descuento_pct": round((previous - price) / previous * 100, 2)
                         if previous and price and previous > 0 else None,
        "precio_m2_min": round(price / smax, 2) if price and smax else None,
        "precio_m2_max": round(price / smin, 2) if price and smin else None,
        "amplitud_superficie_m2": round(smax - smin, 2) if smin is not None and smax is not None else None,
        "es_rango_superficie": int(smin != smax) if smin is not None and smax is not None else None,
        "es_rango_ambientes": int(row.get("ambientes_min") != row.get("ambientes_max"))
                              if row.get("ambientes_min") is not None else None,
        "monoambiente": int("monoambiente" in text or row.get("ambientes_max") == 1),
        "apto_credito": int("apto credito" in text), "balcon": int("balcon" in text),
        "terraza": int("terraza" in text), "pileta": int("pileta" in text or "piscina" in text),
        "parrilla": int("parrilla" in text),
        "cochera_mencionada": int("cochera" in text or "garage" in text),
        "amenities_mencionadas": int("amenities" in text or "sum" in text or "gimnasio" in text),
        "estado_entrega": delivery,
        "cantidad_atributos": len([x for x in str(row.get("atributos_texto") or "").split("|") if x.strip()]),
        "completitud_pct": round(sum(row.get(k) not in (None, "") for k in important) / len(important) * 100, 1),
        "imagen_id": image_id_match.group(1) if image_id_match else None,
        "imagen_extension": ext_match.group(1).lower() if ext_match else None,
    })
    return row


# =============================================================================
# 3. DESCARGA MODERADA
# =============================================================================

def fetch(url: str, config: Config) -> str:
    last_error: Exception | None = None
    for attempt in range(config.retries + 1):
        try:
            request = Request(url, headers=HEADERS)
            with urlopen(request, timeout=config.timeout) as response:
                status = response.status
                body = response.read().decode("utf-8", errors="replace")
            if status != 200:
                raise RuntimeError(f"HTTP {status} en {url}")
            if len(body) < 50_000:
                raise RuntimeError(f"Respuesta demasiado pequeña ({len(body)} bytes) en {url}")
            return body
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < config.retries:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {last_error}")


# =============================================================================
# 4. PARSER DE TARJETAS
# =============================================================================

def get_tipo_operacion(search_url: str) -> str:
    """Clasifica la búsqueda según el tipo de operación de Mercado Libre."""
    url = search_url.lower()

    if "/alquiler-temporal/" in url or "/alquiler_temporal/" in url:
        return "alquiler temporal"
    if "/alquiler/" in url:
        return "alquiler"
    if "/venta/" in url:
        return "venta"

    return "otro"


def parse_cards(source: str, search_url: str, page: int) -> list[dict[str, Any]]:
    tree = html.fromstring(source)
    cards = tree.xpath(
        "//*[contains(concat(' ',normalize-space(@class),' '),"
        "' ui-search-layout__item ')]"
    )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, card in enumerate(cards, start=1):
        links = card.xpath(".//a[contains(@class,'poly-component__title')]/@href")
        if not links:
            links = card.xpath(".//a[contains(@href,'MLA-')]/@href")
        if not links:
            continue
        item_url = clean_item_url(links[0])
        id_match = re.search(r"MLA-?(\d+)", item_url, re.I)
        item_id = f"MLA{id_match.group(1)}" if id_match else item_url
        if item_id in seen:
            continue
        seen.add(item_id)

        title = first_text(card, "poly-component__title")
        price_text = first_text(card, "poly-price__current")
        currency, price = money(price_text)
        location = first_text(card, "poly-component__location")
        seller = first_text(card, "poly-component__seller")
        attrs = [text_of(x) for x in card.xpath(".//*[contains(@class,'poly-attributes_list__item')]")]
        attrs = [x for x in attrs if x]
        joined = " | ".join(attrs)

        amb = next((x for x in attrs if re.search(r"amb", x, re.I)), None)
        baths = next((x for x in attrs if re.search(r"bañ|ban", x, re.I)), None)
        dorms = next((x for x in attrs if re.search(r"dorm", x, re.I)), None)
        area = next((x for x in attrs if re.search(r"m²|m2", x, re.I)), None)
        amb_min, amb_max = integer_range(amb)
        bath_min, bath_max = integer_range(baths)
        dorm_min, dorm_max = integer_range(dorms)
        area_min, area_max = number_range(area)

        images = card.xpath(".//img/@src | .//img/@data-src")
        card_text = text_of(card) or ""
        location_parts = [x.strip() for x in (location or "").split(",") if x.strip()]
        warnings = []
        if not title:
            warnings.append("sin_titulo")
        if price is None:
            warnings.append("sin_precio")

        row = {
            "item_id": item_id, "fuente": "Mercado Libre", "url": item_url,
            "search_url": search_url, "pagina_origen": page,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            "titulo": title, "tipo_propiedad": "departamento",
            "tipo_operacion": get_tipo_operacion(search_url), "moneda": currency, "precio": price,
            "precio_texto": price_text,
            "desde": int(bool(re.search(r"\bdesde\b", card_text, re.I))),
            "inmobiliaria": seller, "direccion": location,
            "barrio": location_parts[-2] if len(location_parts) >= 3 else None,
            "localidad": location_parts[-1] if location_parts else None,
            "provincia": "Capital Federal" if "capital federal" in (location or "").lower() else None,
            "ambientes_min": amb_min, "ambientes_max": amb_max,
            "banios_min": bath_min, "banios_max": bath_max,
            "dormitorios_min": dorm_min, "dormitorios_max": dorm_max,
            "superficie_min_m2": area_min, "superficie_max_m2": area_max,
            "tipo_superficie": "cubierta" if area and "cubiert" in area.lower() else
                               ("total" if area and "total" in area.lower() else None),
            "imagen_principal": images[0] if images else None,
            "destacado": int("Destacado" in card_text),
            "emprendimiento": int("EMPRENDIMIENTO" in card_text.upper()),
            "posesion": first_text(card, "poly-component__possession-date"),
            "unidades_disponibles": parse_arg_number(first_text(card, "poly-component__available-units")),
            "atributos_texto": joined, "texto_tarjeta": card_text,
            "parse_warnings": "|".join(warnings) or None,
        }
        rows.append(enrich_row(row, position=position))
    return rows


# =============================================================================
# 5. JOURNAL, CSV Y CHECKPOINT
# =============================================================================

class Store:
    def __init__(self, folder: Path, checkpoint_every: int):
        folder.mkdir(parents=True, exist_ok=True)
        self.journal = folder / "propiedades_mercadolibre.jsonl"
        self.csv = folder / "propiedades_mercadolibre.csv"
        self.state = folder / "checkpoint_state.json"
        self.every = checkpoint_every
        self.pending = 0
        self.ids = set()
        if self.journal.exists():
            for line in self.journal.read_text(encoding="utf-8").splitlines():
                try:
                    self.ids.add(json.loads(line)["item_id"])
                except (json.JSONDecodeError, KeyError):
                    pass

    def append(self, row: dict[str, Any]) -> bool:
        if row["item_id"] in self.ids:
            return False
        with self.journal.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
        self.ids.add(row["item_id"])
        self.pending += 1
        return True

    def checkpoint(self, last_page: int) -> None:
        rows = []
        if self.journal.exists():
            for line in self.journal.read_text(encoding="utf-8").splitlines():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        tmp = self.csv.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(self.csv)
        self.state.write_text(json.dumps({
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_completed_page": last_page, "unique_properties": len(self.ids),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        self.pending = 0


# =============================================================================
# 6. EJECUCIÓN
# =============================================================================

def run(config: Config) -> None:
    store = Store(config.output_dir, config.checkpoint_every)
    page = config.page_start
    last_completed = page - 1
    added = 0
    while True:
        if config.max_pages is not None and page >= config.page_start + config.max_pages:
            break
        if config.max_properties is not None and added >= config.max_properties:
            break
        page_url = make_page_url(config.search_url, page)
        print(f"Página {page}: {page_url}")
        source = fetch(page_url, config)
        rows = parse_cards(source, config.search_url, page)
        if not rows:
            print("No se encontraron tarjetas. Fin de paginación.")
            break
        new_rows = [r for r in rows if r["item_id"] not in store.ids]
        if config.max_properties is not None:
            new_rows = new_rows[:config.max_properties - added]
        for row in new_rows:
            if store.append(row):
                added += 1
                if store.pending >= store.every:
                    store.checkpoint(page)
        last_completed = page
        store.checkpoint(last_completed)
        print(f"  {len(rows)} tarjetas; {len(new_rows)} nuevas; total ejecución {added}")
        page += 1
        if config.max_pages is None or page < config.page_start + config.max_pages:
            time.sleep(random.uniform(config.min_delay, config.max_delay))
    store.checkpoint(last_completed)
    print(f"Fin. Propiedades nuevas guardadas: {added}")


def positive(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Debe ser mayor que cero")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Scraper de tarjetas de Mercado Libre Inmuebles")
    parser.add_argument("--search-url", default=DEFAULT_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--page-start", type=positive, default=1)
    parser.add_argument("--max-pages", type=positive)
    parser.add_argument("--max-properties", type=positive)
    parser.add_argument("--checkpoint-every", type=positive, default=150)
    parser.add_argument("--min-delay", type=float, default=8.0)
    parser.add_argument("--max-delay", type=float, default=12.0)
    parser.add_argument("--timeout", type=positive, default=30)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    if args.min_delay < 0 or args.max_delay < args.min_delay or args.retries < 0:
        parser.error("Revisá delays y retries")
    run(Config(**vars(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
