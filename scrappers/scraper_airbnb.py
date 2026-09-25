"""Scraper responsable de tarjetas públicas de Airbnb para el TP de Analítica Descriptiva.

Qué hace:
1. Recorre páginas de resultados de una búsqueda configurable.
2. Renderiza cada página con un navegador real (Playwright/Chromium), porque
   Airbnb arma la grilla de resultados con JavaScript del lado del cliente:
   un simple GET con `requests` solo trae el HTML inicial vacío.
3. Extrae información visible de las tarjetas públicas de Airbnb ya renderizadas.
4. Guarda cada alojamiento inmediatamente en JSONL y genera un CSV de checkpoint.
5. Puede reanudarse sin volver a guardar URLs ya procesadas.
6. Conserva el texto completo de la tarjeta para poder recuperar variables después.

REQUISITOS ADICIONALES (antes no hacían falta):
    pip install playwright
    playwright install chromium

IMPORTANTE:
- Está pensado para datos públicos y para un uso académico moderado.
- No usa credenciales, APIs privadas ni intenta resolver CAPTCHAs o bloqueos:
  si el navegador se topa con un CAPTCHA o pantalla de verificación, el
  script corta la ejecución en vez de intentar evadirlo.
- El `robots.txt` de Airbnb no permite crawlear las URLs de búsqueda
  (`/s/*/homes`). Este script lo verifica por defecto y se detiene si no
  pasás `--ignore-robots`. Usar ese flag implica decidir vos, bajo tu
  criterio y el de tu cátedra, correr igual pasando por encima de esa
  restricción explícita del sitio.
- Airbnb tiene sistemas anti-bot activos (Cloudflare/verificaciones) además
  del robots.txt. Aun con el navegador renderizando JS, es esperable que en
  algún momento la sesión sea bloqueada o pedida verificación humana; el
  script no intenta sortear eso, solo lo detecta y corta.
- Airbnb puede cambiar su HTML; por eso los selectores tienen varios respaldos.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import random
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.sync_api import (
    Browser,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


# =============================================================================
# 1. CONFIGURACIÓN
# =============================================================================

BASE_URL = "https://www.airbnb.com.ar"
DEFAULT_SEARCH_URL = f"{BASE_URL}/s/Buenos-Aires--Argentina/homes"
DEFAULT_OUTPUT_DIR = Path("data/raw/airbnb")
PAGE_SIZE = 18

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}

BLOCK_TITLE_PHRASES = (
    "access denied", "acceso denegado", "just a moment",
    "security check", "verificación de seguridad", "verificacion de seguridad",
)

BLOCK_VISIBLE_PHRASES = (
    "verify you are human", "verifique que no es un robot",
    "complete the captcha", "completa el captcha", "security verification",
    "checking your browser", "comprobando su navegador",
)

log = logging.getLogger("airbnb_scraper")


@dataclass(frozen=True)
class Config:
    search_url: str
    output_dir: Path
    page_start: int = 1
    max_pages: int | None = None
    max_properties: int | None = None
    checkpoint_every: int = 100
    min_delay: float = 8.0
    max_delay: float = 12.0
    timeout: int = 30
    retries: int = 2
    respect_robots: bool = True
    headless: bool = True
    nav_timeout_ms: int = 45000
    wait_selector: str = "div[data-testid='card-container'], a[href*='/rooms/']"
    extra_scroll_pause: float = 1.5


# Esquema pensado para que luego sea fácil concatenar con otros scrapers.
FIELDNAMES = [
    "property_id", "fuente", "url", "search_url", "pagina_origen",
    "posicion_pagina", "scraped_at_utc", "http_status", "parse_ok",
    "parse_warnings",
    # Publicación
    "titulo", "tipo_propiedad", "tipo_operacion", "descripcion",
    "anfitrion", "superhost", "estado_publicacion",
    # Precio
    "moneda", "precio", "precio_texto", "precio_por_noche_texto",
    "precio_total_texto", "expensas_texto", "precio_m2_calculado",
    # Ubicación
    "direccion_completa", "barrio", "localidad", "provincia", "pais",
    "codigo_postal", "latitud", "longitud",
    # Distribución
    "huespedes", "dormitorios", "camas", "banios",
    "superficie_total_m2",
    # Airbnb
    "rating", "cantidad_resenas", "categoria_airbnb", "distancia_texto",
    "ubicacion_texto", "amenities_texto", "atributos_texto",
    # Multimedia / trazabilidad
    "cantidad_imagenes", "imagen_principal", "imagen_id",
    "texto_tarjeta", "datos_embebidos_json",
]


# =============================================================================
# 2. LIMPIEZA Y CONVERSIÓN
# =============================================================================

def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize(value: Any) -> str:
    text = clean_text(value) or ""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"[0-9][0-9.,]*", text)
    if not match:
        return None
    raw = match.group(0)
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        decimals = len(raw.rsplit(",", 1)[1])
        raw = raw.replace(",", ".") if decimals <= 2 else raw.replace(",", "")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    elif "." in raw and len(raw.rsplit(".", 1)[1]) == 3:
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_integer(value: Any) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def parse_money(value: Any) -> tuple[str | None, float | None]:
    text = clean_text(value)
    if not text:
        return None, None
    currency = "USD" if re.search(r"US\$|U\$S|USD|d[oó]lares", text, re.I) else "ARS"
    return currency, parse_number(text)


def stable_id(url: str) -> str:
    match = re.search(r"/rooms/(\d+)", url)
    if match:
        return "AIRBNB" + match.group(1)
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


def clean_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


# =============================================================================
# 3. HTTP Y DETECCIÓN DE BLOQUEOS
# =============================================================================

def build_session(config: Config) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=config.retries,
        connect=config.retries,
        read=config.retries,
        status=config.retries,
        backoff_factor=2,
        status_forcelist=(408, 425, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def polite_sleep(config: Config) -> None:
    time.sleep(random.uniform(config.min_delay, config.max_delay))


def detect_block_reason(source: str) -> str | None:
    if not source:
        return None
    soup = BeautifulSoup(source, "html.parser")
    title = clean_text(soup.title) or ""
    for phrase in BLOCK_TITLE_PHRASES:
        if phrase in title.lower():
            return f"titulo:{phrase}"

    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    visible = normalize(soup.get_text(" ", strip=True))
    has_captcha = any(x in source.lower() for x in (
        "g-recaptcha", "h-captcha", "cf-chl-", "challenge-platform", "captcha",
    ))
    for phrase in BLOCK_VISIBLE_PHRASES:
        if phrase in visible and has_captcha:
            return f"texto_visible:{phrase}"
    return None


def allowed_by_robots(url: str, session: requests.Session, timeout: int) -> bool:
    parsed = urlsplit(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    try:
        response = session.get(robots_url, timeout=timeout)
        if response.status_code >= 400:
            log.warning("No se pudo verificar robots.txt (HTTP %s).", response.status_code)
            return True
        parser.parse(response.text.splitlines())
        return parser.can_fetch(USER_AGENT, url)
    except requests.RequestException as exc:
        log.warning("No se pudo consultar robots.txt: %s", exc)
        return True


def fetch_html(page: Page, url: str, config: Config) -> tuple[str | None, int | None]:
    """Navega con un navegador real (Playwright) porque Airbnb arma la grilla
    de resultados con JavaScript del lado del cliente: un GET con `requests`
    solo trae el HTML inicial vacío, sin las tarjetas de alojamientos."""
    status: int | None = None
    try:
        response = page.goto(url, timeout=config.nav_timeout_ms, wait_until="domcontentloaded")
        status = response.status if response else None
        if status == 404:
            return None, status
        if status is not None and status >= 400:
            log.warning("HTTP %s en %s", status, url)
            return None, status

        # Espera a que aparezcan tarjetas de resultados o, si no aparecen,
        # a que quede claro que la página no tiene más contenido.
        try:
            page.wait_for_selector(config.wait_selector, timeout=config.nav_timeout_ms)
        except PlaywrightTimeoutError:
            log.info("No aparecieron tarjetas dentro del timeout en %s.", url)

        # Pequeño scroll para disparar la carga perezosa de tarjetas/imágenes.
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(int(config.extra_scroll_pause * 1000))

        source = page.content()
        block_reason = detect_block_reason(source)
        if block_reason:
            raise RuntimeError(
                "Airbnb mostró un CAPTCHA o bloqueo real "
                f"(señal: {block_reason}). No se intenta eludirlo."
            )
        return source, status
    except PlaywrightTimeoutError as exc:
        log.warning("Timeout de navegación en %s: %s", url, exc)
        return None, status
    finally:
        polite_sleep(config)


# =============================================================================
# 4. PAGINACIÓN Y EXTRACCIÓN DE LINKS
# =============================================================================

def make_page_url(search_url: str, page: int) -> str:
    """Agrega items_offset a la URL sin destruir filtros existentes."""
    parts = urlsplit(search_url)
    query = parse_qs(parts.query, keep_blank_values=True)
    query["items_offset"] = [str(max(0, (page - 1) * PAGE_SIZE))]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def looks_like_listing_url(url: str) -> bool:
    parsed = urlsplit(url)
    if "airbnb." not in parsed.netloc.lower():
        return False
    return bool(re.search(r"/rooms/\d+", parsed.path.lower()))


LISTING_SELECTORS = (
    "div[data-testid='card-container'] a[href*='/rooms/']",
    "div[data-testid='card-container'] a[href]",
    "a[href*='/rooms/']",
)


def extract_listing_links(source: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(source, "html.parser")
    links: list[str] = []
    seen: set[str] = set()

    for selector in LISTING_SELECTORS:
        for tag in soup.select(selector):
            href = tag.get("href")
            if not href:
                continue
            full = clean_url(urljoin(page_url, href))
            if looks_like_listing_url(full) and full not in seen:
                seen.add(full)
                links.append(full)
        if links:
            break
    return links


def find_card_for_url(soup: BeautifulSoup, url: str):
    room_id = re.search(r"/rooms/(\d+)", url)
    if not room_id:
        return None
    marker = room_id.group(1)
    for tag in soup.select("a[href*='/rooms/']"):
        href = tag.get("href", "")
        if marker in href:
            card = tag.find_parent(attrs={"data-testid": "card-container"})
            if card is not None:
                return card
            card = tag.find_parent("div")
            if card is not None:
                return card
    return None


def first_text(card, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        element = card.select_one(selector)
        value = clean_text(element)
        if value:
            return value
    return None


# =============================================================================
# 5. PARSER DE TARJETAS
# =============================================================================

def get_images(card) -> list[str]:
    result = []
    for img in card.select("img"):
        src = img.get("src") or img.get("data-src") or img.get("srcset")
        if src:
            if " " in src and "," in src:
                src = src.split(",")[0].strip().split(" ")[0]
            if src not in result:
                result.append(src)
    return result


def parse_rating(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(?:★\s*)?(\d[.,]\d{1,2})(?:\s|$)", text)
    if not match:
        return None
    return parse_number(match.group(1))


def parse_reviews(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"([0-9][0-9.,]*)\s*(?:reseñas|resenas|reviews)", text, re.I)
    return parse_integer(match.group(1)) if match else None


def parse_guests(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(?:hasta\s*)?([0-9]+)\s*(?:hu[eé]spedes?|guests?)", text, re.I)
    return int(match.group(1)) if match else None


def parse_rooms(text: str | None, label: str) -> int | None:
    if not text:
        return None
    pattern = {
        "dormitorios": r"([0-9]+)\s*(?:dormitorio|dormitorios|habitaci[oó]n|habitaciones|bedroom|bedrooms)",
        "camas": r"([0-9]+)\s*(?:cama|camas|bed|beds)",
        "banios": r"([0-9]+(?:[.,][0-9]+)?)\s*(?:ba[nñ]o|ba[nñ]os|bath|baths)",
    }[label]
    match = re.search(pattern, text, re.I)
    return parse_integer(match.group(1)) if match else None


def get_tipo_operacion(search_url: str) -> str:
    text = normalize(search_url)
    if "alquiler" in text or "rent" in text:
        return "alquiler temporal"
    return "alquiler temporal"


def parse_listing_card(card, url: str, search_url: str, page: int,
                       position: int, status: int | None) -> dict[str, Any]:
    text = clean_text(card) or ""
    normalized = normalize(text)
    images = get_images(card)

    # Airbnb suele presentar el título en aria-label o en textos de la tarjeta.
    title = first_text(card, (
        "[data-testid='listing-card-title']",
        "div[data-testid='listing-card-name']",
        "[aria-label*='Casa']",
        "[aria-label*='Departamento']",
    ))
    if not title:
        aria = card.find(attrs={"aria-label": True})
        title = clean_text(aria.get("aria-label")) if aria else None

    price_text = first_text(card, (
        "[data-testid='price']",
        "span[aria-label*='precio']",
        "span[aria-label*='Price']",
    ))
    if not price_text:
        price_match = re.search(
            r"(?:US\$|U\$S|USD|\$)\s*[0-9][0-9.,]*",
            text,
            re.I,
        )
        price_text = price_match.group(0) if price_match else None

    currency, price = parse_money(price_text)
    rating = parse_rating(text)
    reviews = parse_reviews(text)
    guests = parse_guests(text)
    bedrooms = parse_rooms(text, "dormitorios")
    beds = parse_rooms(text, "camas")
    baths = parse_rooms(text, "banios")

    # Ubicación: se intenta primero con atributos accesibles y después con texto.
    location = first_text(card, (
        "[data-testid='listing-card-subtitle']",
        "[data-testid='listing-card-location']",
    ))

    # Categoría/tipo de alojamiento.
    property_type = None
    for candidate in (
        "casa", "departamento", "habitacion", "habitación", "hotel",
        "hostal", "cabaña", "cabana", "loft", "villa", "casa de huéspedes",
    ):
        if candidate in normalized:
            property_type = candidate
            break

    superhost = int("superhost" in normalized or "superanfitrion" in normalized)
    warnings: list[str] = []
    if not title:
        warnings.append("titulo_no_encontrado")
    if price is None:
        warnings.append("precio_no_encontrado")
    if not images:
        warnings.append("sin_imagen")

    return {
        "property_id": stable_id(url),
        "fuente": "Airbnb",
        "url": url,
        "search_url": search_url,
        "pagina_origen": page,
        "posicion_pagina": position,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "http_status": status,
        "parse_ok": 1,
        "parse_warnings": "|".join(warnings) or None,
        "titulo": title,
        "tipo_propiedad": property_type,
        "tipo_operacion": get_tipo_operacion(search_url),
        "descripcion": None,
        "anfitrion": None,
        "superhost": superhost,
        "estado_publicacion": "publica",
        "moneda": currency,
        "precio": price,
        "precio_texto": price_text,
        "precio_por_noche_texto": price_text,
        "precio_total_texto": None,
        "expensas_texto": None,
        "precio_m2_calculado": None,
        "direccion_completa": location,
        "barrio": None,
        "localidad": None,
        "provincia": None,
        "pais": "Argentina" if ".com.ar" in urlsplit(url).netloc else None,
        "codigo_postal": None,
        "latitud": None,
        "longitud": None,
        "huespedes": guests,
        "dormitorios": bedrooms,
        "camas": beds,
        "banios": baths,
        "superficie_total_m2": None,
        "rating": rating,
        "cantidad_resenas": reviews,
        "categoria_airbnb": None,
        "distancia_texto": None,
        "ubicacion_texto": location,
        "amenities_texto": None,
        "atributos_texto": None,
        "cantidad_imagenes": len(images) or None,
        "imagen_principal": images[0] if images else None,
        "imagen_id": extract_image_id(images[0]) if images else None,
        "texto_tarjeta": text,
        "datos_embebidos_json": None,
    }


def extract_image_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/([0-9a-f]{10,})[_-]", url, re.I)
    return match.group(1) if match else None


def parse_listing_cards(source: str, page_url: str, search_url: str,
                        page: int, status: int | None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(source, "html.parser")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    links = extract_listing_links(source, page_url)
    for position, url in enumerate(links, start=1):
        if url in seen:
            continue
        seen.add(url)
        card = find_card_for_url(soup, url)
        if card is None:
            continue
        rows.append(parse_listing_card(card, url, search_url, page, position, status))
    return rows


# =============================================================================
# 6. PERSISTENCIA Y CHECKPOINT
# =============================================================================

class CheckpointStore:
    def __init__(self, output_dir: Path, checkpoint_every: int):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = output_dir / "propiedades_airbnb_journal.jsonl"
        self.csv_path = output_dir / "propiedades_airbnb.csv"
        self.state_path = output_dir / "checkpoint_state.json"
        self.failed_path = output_dir / "errores.jsonl"
        self.checkpoint_every = checkpoint_every
        self.rows_since_checkpoint = 0
        self.processed_urls = self._load_processed_urls()

    def _load_processed_urls(self) -> set[str]:
        urls: set[str] = set()
        if not self.journal_path.exists():
            return urls
        with self.journal_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                    if row.get("url"):
                        urls.add(row["url"])
                except json.JSONDecodeError:
                    continue
        return urls

    def append(self, row: dict[str, Any]) -> bool:
        if row["url"] in self.processed_urls:
            return False
        with self.journal_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
        self.processed_urls.add(row["url"])
        self.rows_since_checkpoint += 1
        return True

    def record_failure(self, url: str, page: int, reason: str) -> None:
        event = {
            "url": url,
            "page": page,
            "reason": reason,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with self.failed_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def iter_rows(self):
        if not self.journal_path.exists():
            return
        with self.journal_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def checkpoint(self, last_page: int | None = None) -> None:
        tmp_csv = self.csv_path.with_suffix(".csv.tmp")
        rows = list(self.iter_rows())
        latest_by_url = {row["url"]: row for row in rows}

        with tmp_csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            for row in latest_by_url.values():
                writer.writerow(row)
        tmp_csv.replace(self.csv_path)

        state = {
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_page": last_page,
            "unique_properties": len(latest_by_url),
            "journal": str(self.journal_path),
            "csv": str(self.csv_path),
        }
        tmp_state = self.state_path.with_suffix(".json.tmp")
        tmp_state.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_state.replace(self.state_path)
        self.rows_since_checkpoint = 0
        log.info("Checkpoint guardado: %s alojamientos únicos.", len(latest_by_url))


# =============================================================================
# 7. EJECUCIÓN
# =============================================================================

def run(config: Config) -> None:
    store = CheckpointStore(config.output_dir, config.checkpoint_every)
    robots_session = build_session(config)
    scraped_this_run = 0
    empty_pages = 0
    current_page = config.page_start
    last_completed_page = current_page - 1

    try:
        if config.respect_robots and not allowed_by_robots(
            config.search_url, robots_session, config.timeout
        ):
            raise SystemExit("robots.txt no permite acceder a la URL con este agente.")
    finally:
        robots_session.close()

    log.info("Inicio. Ya existen %s alojamientos procesados.", len(store.processed_urls))

    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=config.headless)
        browser_context = browser.new_context(
            user_agent=USER_AGENT,
            locale="es-AR",
            viewport={"width": 1366, "height": 900},
        )
        browser_page = browser_context.new_page()

        try:
            page = current_page
            while True:
                if config.max_pages is not None and page >= config.page_start + config.max_pages:
                    break
                if config.max_properties is not None and scraped_this_run >= config.max_properties:
                    break

                page_url = make_page_url(config.search_url, page)
                log.info("Página %s: %s", page, page_url)
                source, status = fetch_html(browser_page, page_url, config)

                if not source:
                    empty_pages += 1
                    if empty_pages >= 2:
                        log.info("Dos páginas consecutivas sin contenido. Fin de paginación.")
                        break
                    page += 1
                    continue

                links = extract_listing_links(source, page_url)
                new_links = [url for url in links if url not in store.processed_urls]
                log.info("Página %s: %s links; %s nuevos.", page, len(links), len(new_links))

                if not links:
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                else:
                    empty_pages = 0

                if config.max_properties is not None:
                    remaining = config.max_properties - scraped_this_run
                    new_links = new_links[:remaining]

                rows_by_url = {
                    row["url"]: row
                    for row in parse_listing_cards(source, page_url, config.search_url, page, status)
                }

                for url in new_links:
                    row = rows_by_url.get(url)
                    if row:
                        if store.append(row):
                            scraped_this_run += 1
                            log.info("Guardado %s | total ejecución: %s", url, scraped_this_run)
                            if store.rows_since_checkpoint >= config.checkpoint_every:
                                store.checkpoint(last_page=page)
                    else:
                        store.record_failure(url, page, "tarjeta_no_interpretada")

                store.checkpoint(last_page=page)
                last_completed_page = page
                page += 1

        except KeyboardInterrupt:
            log.warning("Interrupción manual. Se realizará un checkpoint final.")
        except RuntimeError as exc:
            log.error("%s", exc)
        finally:
            store.checkpoint(last_page=last_completed_page)
            browser_context.close()
            browser.close()
            log.info("Fin. Alojamientos nuevos guardados: %s", scraped_this_run)


# =============================================================================
# 8. INTERFAZ DE LÍNEA DE COMANDOS
# =============================================================================

def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Debe ser mayor que cero.")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scraper reanudable de Airbnb")
    parser.add_argument("--search-url", default=DEFAULT_SEARCH_URL,
                        help="URL de búsqueda de Airbnb ya filtrada.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--page-start", type=positive_int, default=1)
    parser.add_argument("--max-pages", type=positive_int)
    parser.add_argument("--max-properties", type=positive_int)
    parser.add_argument("--checkpoint-every", type=positive_int, default=100)
    parser.add_argument("--min-delay", type=float, default=8.0)
    parser.add_argument("--max-delay", type=float, default=12.0)
    parser.add_argument("--timeout", type=positive_int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--ignore-robots", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--headful", action="store_true",
                        help="Muestra la ventana del navegador (útil para depurar bloqueos).")
    parser.add_argument("--nav-timeout-ms", type=positive_int, default=45000,
                        help="Timeout de navegación/espera de tarjetas, en milisegundos.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.min_delay < 0 or args.max_delay < args.min_delay or args.retries < 0:
        raise SystemExit("Revisá delays y retries.")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = Config(
        search_url=args.search_url,
        output_dir=args.output_dir,
        page_start=args.page_start,
        max_pages=args.max_pages,
        max_properties=args.max_properties,
        checkpoint_every=args.checkpoint_every,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        timeout=args.timeout,
        retries=args.retries,
        respect_robots=not args.ignore_robots,
        headless=not args.headful,
        nav_timeout_ms=args.nav_timeout_ms,
    )
    log.debug("Configuración: %s", asdict(config))
    run(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
