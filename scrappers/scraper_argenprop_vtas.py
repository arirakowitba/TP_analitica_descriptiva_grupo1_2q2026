"""
Scraper robusto de propiedades de Argenprop para el TP de Analítica Descriptiva.

Qué hace:
1. Recorre páginas de resultados de una URL de búsqueda configurable.
2. Entra en cada publicación y extrae datos visibles, JSON-LD y tablas de atributos.
3. Guarda cada propiedad inmediatamente en JSONL y crea un checkpoint CSV cada N filas.
4. Puede reanudarse sin volver a procesar enlaces ya guardados.
5. Conserva atributos no previstos dentro de `atributos_extra_json`.

Uso responsable: respeta los términos del sitio, robots.txt y una frecuencia moderada.
El programa no intenta resolver ni eludir CAPTCHAs o bloqueos.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =============================================================================
# 1. CONFIGURACIÓN GENERAL
# Aquí se centralizan los valores que normalmente se quieren ajustar.
# =============================================================================

BASE_URL = "https://www.argenprop.com"
DEFAULT_SEARCH_URL = f"{BASE_URL}/departamentos/venta/capital-federal"
DEFAULT_OUTPUT_DIR = Path("data/raw/argenprop")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 TP-Analitica-Descriptiva/1.0"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}

# Frases que aparecen cuando el usuario está realmente frente a un desafío.
# La existencia de la librería g-recaptcha o de data-sitekey NO alcanza: muchos
# sitios las cargan preventivamente dentro de páginas completamente normales.
BLOCK_TITLE_PHRASES = (
    "access denied", "acceso denegado", "just a moment", "security check",
    "verificación de seguridad", "verificacion de seguridad",
)

BLOCK_VISIBLE_PHRASES = (
    "verify you are human", "verifique que no es un robot",
    "completa el captcha", "complete el captcha", "security verification",
    "checking your browser", "comprobando su navegador",
)

log = logging.getLogger("argenprop_scraper")


@dataclass(frozen=True)
class Config:
    """Parámetros de una ejecución del scraper."""

    search_url: str
    output_dir: Path
    checkpoint_every: int = 150
    page_start: int = 1
    max_pages: int | None = None
    max_properties: int | None = None
    workers: int = 4
    min_delay: float = 1.2
    max_delay: float = 2.5
    timeout: int = 25
    retries: int = 4
    respect_robots: bool = True
    listing_only: bool = False


# =============================================================================
# 2. ESQUEMA DE SALIDA
# Son columnas estables para análisis; lo desconocido se guarda también en JSON.
# =============================================================================

FIELDNAMES = [
    # Identidad y trazabilidad
    "property_id", "fuente", "url", "scraped_at_utc", "search_url",
    "pagina_origen", "http_status", "parse_ok", "parse_warnings",
    # Publicación
    "titulo", "descripcion", "tipo_operacion", "tipo_propiedad",
    "estado_publicacion", "fecha_publicacion", "inmobiliaria", "seller_id",
    # Precio
    "moneda", "precio", "precio_texto", "expensas_moneda", "expensas",
    "expensas_texto", "precio_m2_calculado",
    # Ubicación
    "direccion_completa", "calle", "altura", "piso", "unidad",
    "barrio", "localidad", "partido", "provincia", "pais",
    "codigo_postal", "latitud", "longitud",
    # Dimensiones y distribución
    "ambientes", "dormitorios", "banios", "toilettes", "cocheras",
    "superficie_total_m2", "superficie_cubierta_m2",
    "superficie_descubierta_m2", "superficie_semicubierta_m2",
    "superficie_terreno_m2", "frente_m", "fondo_m",
    # Características de la unidad y edificio
    "antiguedad_anios", "estado_inmueble", "disposicion", "orientacion",
    "luminosidad", "cantidad_plantas", "cantidad_pisos_edificio",
    "departamentos_por_piso", "apto_credito", "apto_profesional",
    "permite_mascotas", "accesibilidad", "amoblado",
    # Amenities y servicios como variables binarias
    "balcon", "terraza", "patio", "jardin", "parrilla", "pileta",
    "sum", "gimnasio", "sauna", "laundry", "baulera", "ascensor",
    "seguridad_24h", "vigilancia", "aire_acondicionado", "calefaccion",
    "losa_radiante", "gas_natural", "agua_corriente", "electricidad",
    "cloaca", "internet", "vista_rio", "vista_abierta", "reciclado",
    "a_refaccionar",
    # Multimedia y cobertura
    "cantidad_imagenes", "imagen_principal", "video_url", "tour_virtual_url",
    "cantidad_atributos_extra", "atributos_extra_json", "jsonld_raw",
]


# =============================================================================
# 3. FUNCIONES DE LIMPIEZA Y CONVERSIÓN
# Convierten texto desordenado en valores comparables.
# =============================================================================

def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_key(value: Any) -> str:
    text = clean_text(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def parse_number(value: Any) -> float | None:
    """Interpreta números argentinos: 1.250,50 -> 1250.50."""
    if value is None:
        return None
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"-?[0-9][0-9.,]*", text)
    if not match:
        return None
    number = match.group(0)
    if "." in number and "," in number:
        number = number.replace(".", "").replace(",", ".")
    elif number.count(".") > 1:
        number = number.replace(".", "")
    elif number.count(",") > 1:
        number = number.replace(",", "")
    elif "," in number:
        decimals = len(number.rsplit(",", 1)[1])
        number = number.replace(",", ".") if decimals <= 2 else number.replace(",", "")
    elif "." in number:
        decimals = len(number.rsplit(".", 1)[1])
        if decimals == 3:
            number = number.replace(".", "")
    try:
        return float(number)
    except ValueError:
        return None


def parse_integer(value: Any) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def parse_money(value: Any) -> tuple[str | None, float | None, str | None]:
    text = clean_text(value)
    if not text:
        return None, None, None
    lower = text.lower()
    currency = None
    if re.search(r"\b(usd|u\$s|us\$|d[oó]lares?)\b", lower):
        currency = "USD"
    elif re.search(r"\b(ars|pesos?)\b|\$", lower):
        currency = "ARS"
    return currency, parse_number(text), text


def parse_bool(value: Any) -> int | None:
    if value is None:
        return None
    text = normalize_key(value)
    if text in {"si", "true", "1", "incluido", "disponible", "apto"}:
        return 1
    if text in {"no", "false", "0", "sin", "no_apto"}:
        return 0
    return None


def first_not_none(*values: Any) -> Any:
    return next((v for v in values if v not in (None, "", [], {})), None)


def stable_property_id(url: str, external_id: Any = None) -> str:
    source = str(external_id or url).strip()
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:20]


def parse_address(text: Any) -> dict[str, Any]:
    result = {"direccion_completa": clean_text(text), "calle": None, "altura": None,
              "piso": None, "unidad": None}
    raw = result["direccion_completa"] or ""
    piso = re.search(r"\b(?:piso|p\.?)[\s:]*([A-Za-z0-9-]+)", raw, re.I)
    unidad = re.search(r"\b(?:depto|dpto|unidad|uf)[\s:]*([A-Za-z0-9-]+)", raw, re.I)
    if piso:
        result["piso"] = piso.group(1)
    if unidad:
        result["unidad"] = unidad.group(1)
    base = re.split(r",|\bpiso\b|\bdpto\b|\bdepto\b|\bunidad\b", raw, maxsplit=1, flags=re.I)[0]
    match = re.match(r"^(.*?)\s+(\d{1,6})(?:\s|$)", base.strip())
    if match:
        result["calle"], result["altura"] = match.group(1).strip(), match.group(2)
    elif base:
        result["calle"] = base.strip()
    return result


# =============================================================================
# 4. CLIENTE HTTP Y CUIDADO DEL SITIO
# Agrega reintentos, pausas, timeout y detección de bloqueos.
# =============================================================================

def build_session(config: Config) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=config.retries,
        connect=config.retries,
        read=config.retries,
        status=config.retries,
        backoff_factor=1.2,
        # En Argenprop, un 202 pequeño suele ser una respuesta intermedia de
        # protección, no una página de resultados lista para analizar.
        status_forcelist=(202, 408, 425, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=config.workers + 2,
                          pool_maxsize=config.workers + 2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def polite_sleep(config: Config) -> None:
    time.sleep(random.uniform(config.min_delay, config.max_delay))


def detect_block_reason(html: str) -> str | None:
    """Detecta una página de bloqueo, no la mera carga de scripts de CAPTCHA."""
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    title = clean_text(soup.title) or ""
    title_lower = title.lower()

    # Un título explícito de acceso denegado o desafío es evidencia suficiente.
    for phrase in BLOCK_TITLE_PHRASES:
        if phrase in title_lower:
            return f"titulo:{phrase}"

    # Se mira solo texto visible. Los scripts y estilos pueden mencionar
    # reCAPTCHA aunque la página de propiedades haya cargado normalmente.
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    visible_text = clean_text(soup.get_text(" ", strip=True)) or ""
    visible_lower = visible_text.lower()
    has_captcha_widget = any(marker in html.lower() for marker in (
        "g-recaptcha", "h-captcha", "cf-chl-", "challenge-platform"
    ))
    for phrase in BLOCK_VISIBLE_PHRASES:
        if phrase in visible_lower and has_captcha_widget:
            return f"texto_visible:{phrase}"
    return None


def is_blocked(html: str) -> bool:
    """Compatibilidad: indica si la respuesta parece ser realmente un bloqueo."""
    return detect_block_reason(html) is not None


def allowed_by_robots(url: str, session: requests.Session, timeout: int) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
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


def fetch_html(session: requests.Session, url: str, config: Config) -> tuple[str | None, int | None]:
    try:
        response = session.get(url, timeout=config.timeout, allow_redirects=True)
        status = response.status_code
        if status == 202:
            # No convertir una respuesta intermedia en una página vacía: eso
            # haría que el scraper creyera erróneamente que terminó el listado.
            diagnostic_dir = config.output_dir / "diagnosticos"
            diagnostic_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
            diagnostic_path = diagnostic_dir / f"http_202_{stamp}_{url_hash}.html"
            diagnostic_path.write_text(response.text, encoding="utf-8", errors="replace")
            raise RuntimeError(
                "Argenprop devolvió HTTP 202 después de los reintentos. Es una "
                "respuesta intermedia o una protección temporal, no una página "
                "vacía. No se avanzó el checkpoint. Esperá unos minutos y volvé "
                f"a ejecutar. Diagnóstico: {diagnostic_path}"
            )
        if status == 404:
            return None, status
        if status >= 400:
            log.warning("HTTP %s en %s", status, url)
            return None, status
        html = response.text
        block_reason = detect_block_reason(html)
        if block_reason:
            raise RuntimeError(
                "El sitio mostró un CAPTCHA o bloqueo real "
                f"(señal detectada: {block_reason}). Se detiene la ejecución; "
                "no se intenta eludirlo. Probá más tarde o reducí la frecuencia."
            )
        return html, status
    except requests.RequestException as exc:
        log.warning("Error de conexión en %s: %s", url, exc)
        return None, None
    finally:
        polite_sleep(config)


# =============================================================================
# 5. EXTRACCIÓN DE LINKS DE LAS PÁGINAS DE RESULTADOS
# Usa varios selectores para resistir cambios pequeños de HTML.
# =============================================================================

LISTING_SELECTORS = (
    "div.listing__item a.card[href]",
    "div.listing__item a[href]",
    "article a[href*='/'][href]",
    "a[href*='departamento'][href]",
    "a[href*='casa'][href]",
    "a[href*='ph-'][href]",
)


def make_page_url(search_url: str, page: int) -> str:
    if page <= 1:
        return search_url
    # Argenprop suele aceptar el sufijo pagina-N.
    clean = search_url.rstrip("/")
    clean = re.sub(r"/pagina-\d+$", "", clean)
    return f"{clean}/pagina-{page}"


def looks_like_property_url(url: str) -> bool:
    parsed = urlparse(url)
    if "argenprop.com" not in parsed.netloc:
        return False
    excluded = ("/buscar", "/emprendimientos", "/inmobiliarias", "/blog", "/ayuda")
    return not any(part in parsed.path.lower() for part in excluded) and len(parsed.path) > 12


def extract_listing_links(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    seen: set[str] = set()
    for selector in LISTING_SELECTORS:
        for tag in soup.select(selector):
            href = tag.get("href")
            if not href:
                continue
            full = urljoin(page_url, href).split("#", 1)[0]
            full = re.sub(r"\?.*$", "", full)
            if looks_like_property_url(full) and full not in seen:
                seen.add(full)
                links.append(full)
        if links and selector.startswith("div.listing__item"):
            break
    return links


def _card_value(card: Any, *selectors: str) -> str | None:
    """Devuelve el primer texto no vacío encontrado dentro de una tarjeta."""
    for selector in selectors:
        element = card.select_one(selector)
        value = clean_text(element)
        if value:
            return value
    return None


def parse_listing_cards(html: str, page_url: str, search_url: str,
                        page: int, status: int | None) -> list[dict[str, Any]]:
    """Convierte las tarjetas del listado en filas sin abrir cada publicación."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Se parte de los mismos enlaces ya validados y se busca su contenedor más
    # cercano. Esto tolera que el portal cambie nombres de clases secundarios.
    for url in extract_listing_links(html, page_url):
        path = urlparse(url).path
        anchor = soup.select_one(f'a[href="{path}"]') or soup.select_one(f'a[href="{url}"]')
        if anchor is None:
            anchor = next((a for a in soup.select("a[href]")
                           if urljoin(page_url, a.get("href", "")).split("#", 1)[0]
                           .split("?", 1)[0] == url), None)
        if anchor is None or url in seen:
            continue
        seen.add(url)

        card = anchor.find_parent("article")
        if card is None:
            card = anchor.find_parent(class_=re.compile(r"listing__item|card|posting", re.I))
        if card is None:
            card = anchor.parent

        card_text = clean_text(card) or ""
        title = _card_value(card, "h2", "h3", "[class*='title']", "[class*='titulo']")
        price_text = _card_value(card, "[class*='price']", "[class*='precio']")
        if not price_text:
            match = re.search(r"(?:USD|U\$S|US\$|ARS|\$)\s*[0-9][0-9.,]*", card_text, re.I)
            price_text = match.group(0) if match else None
        currency, price, price_original = parse_money(price_text)

        exp_match = re.search(
            r"expensas?\s*(?:(?:USD|U\$S|US\$|ARS|\$)\s*)?[0-9][0-9.,]*",
            card_text, re.I,
        )
        exp_text = exp_match.group(0) if exp_match else None
        exp_currency, expenses, exp_original = parse_money(exp_text)
        address_text = _card_value(
            card, "[class*='address']", "[class*='direccion']",
            "[class*='location']", "[class*='ubicacion']",
        )

        def card_int(pattern: str) -> int | None:
            match = re.search(pattern, card_text, re.I)
            return parse_integer(match.group(1)) if match else None

        def card_area(pattern: str) -> float | None:
            match = re.search(pattern, card_text, re.I)
            return parse_number(match.group(1)) if match else None

        total_area = card_area(r"([0-9][0-9.,]*)\s*m(?:²|2)\s*(?:totales?|total)?")
        covered_area = card_area(r"([0-9][0-9.,]*)\s*m(?:²|2)\s*(?:cubiertos?|cubierta)")
        image = card.select_one("img")
        seller = _card_value(card, "[class*='seller']", "[class*='inmobiliaria']", "[class*='publisher']")

        result: dict[str, Any] = {field: None for field in FIELDNAMES}
        result.update({
            "property_id": stable_property_id(url), "fuente": "Argenprop",
            "url": url, "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            "search_url": search_url, "pagina_origen": page, "http_status": status,
            "parse_ok": 1,
            "parse_warnings": "modo_listado_sin_ficha_detallada",
            "titulo": title, "descripcion": None,
            "tipo_operacion": "venta" if "/venta/" in search_url.lower() else
                              ("alquiler" if "/alquiler/" in search_url.lower() else None),
            "tipo_propiedad": search_url.split("/", 4)[3].rstrip("s")
                              if len(search_url.split("/")) > 3 else None,
            "inmobiliaria": seller,
            "moneda": currency, "precio": price, "precio_texto": price_original,
            "expensas_moneda": exp_currency, "expensas": expenses,
            "expensas_texto": exp_original,
            "direccion_completa": address_text,
            **parse_address(address_text),
            "ambientes": card_int(r"([0-9]+)\s*(?:ambientes?|amb\b)"),
            "dormitorios": card_int(r"([0-9]+)\s*(?:dormitorios?|dorm\b)"),
            "banios": card_int(r"([0-9]+)\s*(?:baños?|banos?)"),
            "cocheras": card_int(r"([0-9]+)\s*(?:cocheras?|garages?)"),
            "superficie_total_m2": total_area,
            "superficie_cubierta_m2": covered_area,
            "imagen_principal": (image.get("src") or image.get("data-src")) if image else None,
            "cantidad_imagenes": len(card.select("img")) or None,
            "cantidad_atributos_extra": 1,
            "atributos_extra_json": json.dumps({"texto_tarjeta": card_text}, ensure_ascii=False),
        })
        if price and total_area and total_area > 0:
            result["precio_m2_calculado"] = round(price / total_area, 2)
        rows.append(result)
    return rows


# =============================================================================
# 6. EXTRACCIÓN DE JSON-LD Y ATRIBUTOS GENÉRICOS
# Captura metadatos estructurados y cualquier par "campo: valor" disponible.
# =============================================================================

def flatten_jsonld(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from flatten_jsonld(child)
    elif isinstance(value, list):
        for child in value:
            yield from flatten_jsonld(child)


def extract_jsonld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for tag in soup.select("script[type='application/ld+json']"):
        try:
            raw = tag.string or tag.get_text()
            parsed = json.loads(raw)
            objects.extend(flatten_jsonld(parsed))
        except (json.JSONDecodeError, TypeError):
            continue
    return objects


def choose_property_jsonld(objects: list[dict[str, Any]]) -> dict[str, Any]:
    preferred = ("RealEstateListing", "Apartment", "House", "Residence", "Product", "Offer")
    for wanted in preferred:
        for obj in objects:
            obj_type = obj.get("@type", "")
            types = obj_type if isinstance(obj_type, list) else [obj_type]
            if wanted in types:
                return obj
    return objects[0] if objects else {}


def extract_key_values(soup: BeautifulSoup) -> dict[str, str]:
    pairs: dict[str, str] = {}

    # Tablas y listas de definición.
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) == 2:
            key, value = clean_text(cells[0]), clean_text(cells[1])
            if key and value and len(key) <= 80:
                pairs[key] = value
    for dt in soup.select("dt"):
        dd = dt.find_next_sibling("dd")
        key, value = clean_text(dt), clean_text(dd)
        if key and value:
            pairs[key] = value

    # Componentes habituales de características.
    selectors = (
        "[class*='feature']", "[class*='caracter']", "[class*='detail']",
        "[class*='attribute']", "[class*='spec']", "[class*='property'] li",
    )
    for selector in selectors:
        for element in soup.select(selector):
            text = clean_text(element)
            if not text or len(text) > 180:
                continue
            if ":" in text:
                key, value = [part.strip() for part in text.split(":", 1)]
                if 1 < len(key) <= 80 and value:
                    pairs.setdefault(key, value)
            else:
                # Un ítem aislado como "Balcón" se conserva como atributo presente.
                words = text.split()
                if 1 <= len(words) <= 5:
                    pairs.setdefault(text, "Sí")
    return pairs


def normalized_attributes(pairs: dict[str, str]) -> dict[str, str]:
    return {normalize_key(key): value for key, value in pairs.items() if normalize_key(key)}


def attr(attrs: dict[str, str], *names: str) -> str | None:
    for name in names:
        key = normalize_key(name)
        if key in attrs:
            return attrs[key]
    # Segundo intento: coincidencia parcial controlada.
    for name in names:
        wanted = normalize_key(name)
        for key, value in attrs.items():
            if wanted and (wanted in key or key in wanted):
                return value
    return None


# =============================================================================
# 7. MAPEO A COLUMNAS ANALÍTICAS
# Transforma nombres variables del portal en un esquema común.
# =============================================================================

BINARY_TERMS = {
    "balcon": ("balcon",), "terraza": ("terraza",), "patio": ("patio",),
    "jardin": ("jardin",), "parrilla": ("parrilla",),
    "pileta": ("pileta", "piscina"), "sum": ("sum", "salon de usos multiples"),
    "gimnasio": ("gimnasio", "gym"), "sauna": ("sauna",),
    "laundry": ("laundry", "lavanderia"), "baulera": ("baulera",),
    "ascensor": ("ascensor",), "seguridad_24h": ("seguridad 24", "vigilancia 24"),
    "vigilancia": ("vigilancia",), "aire_acondicionado": ("aire acondicionado",),
    "calefaccion": ("calefaccion", "caldera"), "losa_radiante": ("losa radiante",),
    "gas_natural": ("gas natural",), "agua_corriente": ("agua corriente",),
    "electricidad": ("electricidad", "luz"), "cloaca": ("cloaca",),
    "internet": ("internet", "wifi"), "vista_rio": ("vista al rio", "vista al río"),
    "vista_abierta": ("vista abierta", "vista panoramica"),
    "reciclado": ("reciclado", "reciclada", "refaccionado a nuevo"),
    "a_refaccionar": ("a refaccionar", "para reciclar", "estado original"),
}


def infer_binary_features(attrs: dict[str, str], description: str | None) -> dict[str, int | None]:
    haystack = normalize_key(" ".join([description or ""] + [f"{k} {v}" for k, v in attrs.items()]))
    result: dict[str, int | None] = {}
    for column, terms in BINARY_TERMS.items():
        explicit = first_not_none(*(attr(attrs, term) for term in terms))
        parsed = parse_bool(explicit)
        if parsed is not None:
            result[column] = parsed
        else:
            result[column] = int(any(normalize_key(term) in haystack for term in terms))
    return result


def get_meta(soup: BeautifulSoup, *selectors: str) -> str | None:
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            return clean_text(tag.get("content") or tag.get_text(" ", strip=True))
    return None


def jsonld_offer(data: dict[str, Any]) -> dict[str, Any]:
    offer = data.get("offers") or data.get("offer") or {}
    if isinstance(offer, list):
        return offer[0] if offer else {}
    return offer if isinstance(offer, dict) else {}


def jsonld_address(data: dict[str, Any]) -> dict[str, Any]:
    address = data.get("address") or data.get("location", {}).get("address", {}) if isinstance(data.get("location"), dict) else data.get("address", {})
    return address if isinstance(address, dict) else {}


def parse_property(html: str, url: str, search_url: str, page: int,
                   status: int | None) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    jsonld_objects = extract_jsonld(soup)
    data = choose_property_jsonld(jsonld_objects)
    offer = jsonld_offer(data)
    address_ld = jsonld_address(data)
    raw_pairs = extract_key_values(soup)
    attrs = normalized_attributes(raw_pairs)
    warnings: list[str] = []

    title = first_not_none(
        data.get("name"), get_meta(soup, "meta[property='og:title']", "h1")
    )
    description = first_not_none(
        data.get("description"),
        get_meta(soup, "meta[name='description']", "meta[property='og:description']",
                 "[class*='description']")
    )
    price_text = first_not_none(
        offer.get("price"), attr(attrs, "precio", "valor"),
        get_meta(soup, "meta[property='product:price:amount']", "[class*='price']")
    )
    currency, price, price_original = parse_money(price_text)
    currency = first_not_none(offer.get("priceCurrency"), currency)

    exp_text = attr(attrs, "expensas", "gastos comunes")
    exp_currency, expenses, exp_original = parse_money(exp_text)
    address_text = first_not_none(
        address_ld.get("streetAddress"), attr(attrs, "direccion", "ubicacion"),
        get_meta(soup, "[class*='address']", "[class*='location']")
    )
    address = parse_address(address_text)

    geo = data.get("geo") if isinstance(data.get("geo"), dict) else {}
    if not geo:
        geo = next((obj for obj in jsonld_objects if obj.get("@type") == "GeoCoordinates"), {})

    images = data.get("image") or []
    if isinstance(images, str):
        images = [images]
    elif isinstance(images, dict):
        images = [images.get("url")]
    images = [x for x in images if x]

    result: dict[str, Any] = {field: None for field in FIELDNAMES}
    result.update({
        "property_id": stable_property_id(url, first_not_none(data.get("sku"), data.get("productID"))),
        "fuente": "Argenprop", "url": url,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "search_url": search_url, "pagina_origen": page, "http_status": status,
        "parse_ok": 1, "titulo": clean_text(title), "descripcion": clean_text(description),
        "tipo_operacion": attr(attrs, "tipo de operacion", "operacion"),
        "tipo_propiedad": first_not_none(data.get("category"), attr(attrs, "tipo de propiedad", "tipo de unidad")),
        "estado_publicacion": offer.get("availability"),
        "fecha_publicacion": attr(attrs, "fecha de publicacion", "publicado"),
        "inmobiliaria": clean_text(data.get("seller", {}).get("name")) if isinstance(data.get("seller"), dict) else None,
        "seller_id": data.get("seller", {}).get("identifier") if isinstance(data.get("seller"), dict) else None,
        "moneda": currency, "precio": price, "precio_texto": price_original,
        "expensas_moneda": exp_currency, "expensas": expenses, "expensas_texto": exp_original,
        **address,
        "barrio": attr(attrs, "barrio"),
        "localidad": first_not_none(address_ld.get("addressLocality"), attr(attrs, "localidad")),
        "partido": attr(attrs, "partido"),
        "provincia": first_not_none(address_ld.get("addressRegion"), attr(attrs, "provincia")),
        "pais": first_not_none(address_ld.get("addressCountry"), "Argentina"),
        "codigo_postal": first_not_none(address_ld.get("postalCode"), attr(attrs, "codigo postal")),
        "latitud": parse_number(first_not_none(geo.get("latitude"), attr(attrs, "latitud"))),
        "longitud": parse_number(first_not_none(geo.get("longitude"), attr(attrs, "longitud"))),
        "ambientes": parse_integer(attr(attrs, "cantidad de ambientes", "ambientes")),
        "dormitorios": parse_integer(attr(attrs, "cantidad de dormitorios", "dormitorios")),
        "banios": parse_integer(attr(attrs, "cantidad de banos", "banos")),
        "toilettes": parse_integer(attr(attrs, "cantidad de toilettes", "toilettes")),
        "cocheras": parse_integer(attr(attrs, "cantidad de cocheras", "cocheras", "garage")),
        "superficie_total_m2": parse_number(attr(attrs, "superficie total", "superficie")),
        "superficie_cubierta_m2": parse_number(attr(attrs, "superficie cubierta")),
        "superficie_descubierta_m2": parse_number(attr(attrs, "superficie descubierta")),
        "superficie_semicubierta_m2": parse_number(attr(attrs, "superficie semicubierta")),
        "superficie_terreno_m2": parse_number(attr(attrs, "superficie terreno", "superficie del terreno")),
        "frente_m": parse_number(attr(attrs, "frente")), "fondo_m": parse_number(attr(attrs, "fondo")),
        "antiguedad_anios": parse_integer(attr(attrs, "antiguedad")),
        "estado_inmueble": attr(attrs, "estado del inmueble", "estado"),
        "disposicion": attr(attrs, "disposicion"), "orientacion": attr(attrs, "orientacion"),
        "luminosidad": attr(attrs, "luminosidad"),
        "cantidad_plantas": parse_integer(attr(attrs, "cantidad de plantas", "plantas")),
        "cantidad_pisos_edificio": parse_integer(attr(attrs, "cantidad de pisos", "pisos del edificio")),
        "departamentos_por_piso": parse_integer(attr(attrs, "departamentos por piso", "unidades por piso")),
        "apto_credito": parse_bool(attr(attrs, "apto credito")),
        "apto_profesional": parse_bool(attr(attrs, "apto profesional")),
        "permite_mascotas": parse_bool(attr(attrs, "permite mascotas", "mascotas")),
        "accesibilidad": parse_bool(attr(attrs, "acceso para movilidad reducida", "accesibilidad")),
        "amoblado": parse_bool(attr(attrs, "amoblado", "amueblado")),
        "cantidad_imagenes": len(images) or None,
        "imagen_principal": first_not_none(data.get("primaryImageOfPage", {}).get("contentUrl") if isinstance(data.get("primaryImageOfPage"), dict) else None, images[0] if images else None, get_meta(soup, "meta[property='og:image']")),
        "video_url": attr(attrs, "video", "video url"),
        "tour_virtual_url": attr(attrs, "tour virtual", "recorrido virtual"),
        "cantidad_atributos_extra": len(raw_pairs),
        "atributos_extra_json": json.dumps(raw_pairs, ensure_ascii=False, sort_keys=True),
        "jsonld_raw": json.dumps(data, ensure_ascii=False, sort_keys=True),
    })
    result.update(infer_binary_features(attrs, result["descripcion"]))

    total_surface = result.get("superficie_total_m2")
    if price and total_surface and total_surface > 0:
        result["precio_m2_calculado"] = round(price / total_surface, 2)
    if not title:
        warnings.append("titulo_no_encontrado")
    if price is None:
        warnings.append("precio_no_encontrado")
    if not raw_pairs:
        warnings.append("sin_tabla_atributos")
    result["parse_warnings"] = "|".join(warnings) or None
    return result


# =============================================================================
# 8. PERSISTENCIA Y CHECKPOINTS
# JSONL se escribe por fila; CSV y estado se actualizan cada ~150 registros.
# =============================================================================

class CheckpointStore:
    def __init__(self, output_dir: Path, checkpoint_every: int):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = output_dir / "propiedades_journal.jsonl"
        self.csv_path = output_dir / "propiedades_argenprop.csv"
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
                    log.warning("Se ignoró una línea incompleta al final del journal.")
        return urls

    def append(self, row: dict[str, Any]) -> None:
        with self.journal_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
        self.processed_urls.add(row["url"])
        self.rows_since_checkpoint += 1
        if self.rows_since_checkpoint >= self.checkpoint_every:
            self.checkpoint(last_page=row.get("pagina_origen"))

    def record_failure(self, url: str, page: int, reason: str) -> None:
        event = {"url": url, "page": page, "reason": reason,
                 "timestamp_utc": datetime.now(timezone.utc).isoformat()}
        with self.failed_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def iter_rows(self) -> Iterable[dict[str, Any]]:
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
        latest_by_url: dict[str, dict[str, Any]] = {}
        for row in self.iter_rows():
            latest_by_url[row["url"]] = row
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
        log.info("Checkpoint guardado: %s propiedades únicas.", len(latest_by_url))


# =============================================================================
# 9. ORQUESTACIÓN DEL SCRAPING
# Coordina listados, detalles, reanudación y corte seguro.
# =============================================================================

def scrape_one(url: str, page: int, config: Config) -> tuple[dict[str, Any] | None, str | None]:
    session = build_session(config)
    try:
        html, status = fetch_html(session, url, config)
        if not html:
            return None, f"sin_html_http_{status}"
        return parse_property(html, url, config.search_url, page, status), None
    except Exception as exc:  # registra una propiedad problemática sin frenar todas
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        session.close()


def run(config: Config) -> None:
    store = CheckpointStore(config.output_dir, config.checkpoint_every)
    list_session = build_session(config)
    scraped_this_run = 0
    empty_pages = 0

    if config.respect_robots and not allowed_by_robots(config.search_url, list_session, config.timeout):
        raise SystemExit("robots.txt no permite acceder a la URL con este agente. Ejecución cancelada.")

    log.info("Inicio. Ya existen %s enlaces procesados.", len(store.processed_urls))
    page = config.page_start
    # Solo se actualiza al completar de verdad una página. Una respuesta 202,
    # un bloqueo o una interrupción no deben hacer avanzar la reanudación.
    last_completed_page = config.page_start - 1
    try:
        while True:
            if config.max_pages is not None and page >= config.page_start + config.max_pages:
                break
            if config.max_properties is not None and scraped_this_run >= config.max_properties:
                break

            page_url = make_page_url(config.search_url, page)
            log.info("Página %s: %s", page, page_url)
            html, listing_status = fetch_html(list_session, page_url, config)
            if not html:
                empty_pages += 1
                if empty_pages >= 2:
                    log.info("Dos páginas consecutivas sin contenido. Fin de paginación.")
                    break
                page += 1
                continue

            links = extract_listing_links(html, page_url)
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

            if config.listing_only:
                rows_by_url = {
                    row["url"]: row
                    for row in parse_listing_cards(
                        html, page_url, config.search_url, page, listing_status
                    )
                }
                for url in new_links:
                    row = rows_by_url.get(url)
                    if row:
                        store.append(row)
                        scraped_this_run += 1
                        log.info("Guardada desde tarjeta %s | total ejecución: %s",
                                 url, scraped_this_run)
                    else:
                        store.record_failure(url, page, "tarjeta_no_interpretada")
                store.checkpoint(last_page=page)
                last_completed_page = page
                page += 1
                continue

            with ThreadPoolExecutor(max_workers=config.workers) as executor:
                futures = {executor.submit(scrape_one, url, page, config): url for url in new_links}
                for future in as_completed(futures):
                    url = futures[future]
                    row, error = future.result()
                    if row:
                        store.append(row)
                        scraped_this_run += 1
                        log.info("Guardada %s | total ejecución: %s", url, scraped_this_run)
                    else:
                        store.record_failure(url, page, error or "error_desconocido")
                        log.warning("No se pudo extraer %s: %s", url, error)
            store.checkpoint(last_page=page)
            last_completed_page = page
            page += 1
    except KeyboardInterrupt:
        log.warning("Interrupción manual. Se realizará un checkpoint final.")
    finally:
        store.checkpoint(last_page=last_completed_page)
        list_session.close()
        log.info("Fin. Propiedades nuevas guardadas: %s", scraped_this_run)


# =============================================================================
# 10. INTERFAZ DE LÍNEA DE COMANDOS
# Permite cambiar alcance y velocidad sin editar el archivo.
# =============================================================================

def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Debe ser mayor que cero.")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scraper reanudable de Argenprop")
    parser.add_argument("--search-url", default=DEFAULT_SEARCH_URL,
                        help="URL de búsqueda de Argenprop ya filtrada.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--checkpoint-every", type=positive_int, default=150)
    parser.add_argument("--page-start", type=positive_int, default=1)
    parser.add_argument("--max-pages", type=positive_int)
    parser.add_argument("--max-properties", type=positive_int)
    parser.add_argument("--workers", type=positive_int, default=4)
    parser.add_argument("--min-delay", type=float, default=1.2)
    parser.add_argument("--max-delay", type=float, default=2.5)
    parser.add_argument("--timeout", type=positive_int, default=25)
    parser.add_argument("--retries", type=positive_int, default=4)
    parser.add_argument(
        "--listing-only", action="store_true",
        help="Extrae las tarjetas del listado sin abrir las fichas individuales.",
    )
    parser.add_argument("--ignore-robots", action="store_true",
                        help="Usar solo si ya verificaste manualmente que el acceso está permitido.")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.min_delay < 0 or args.max_delay < args.min_delay:
        raise SystemExit("Los delays deben ser positivos y max-delay >= min-delay.")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    config = Config(
        search_url=args.search_url,
        output_dir=args.output_dir,
        checkpoint_every=args.checkpoint_every,
        page_start=args.page_start,
        max_pages=args.max_pages,
        max_properties=args.max_properties,
        workers=min(args.workers, 8),
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        timeout=args.timeout,
        retries=args.retries,
        respect_robots=not args.ignore_robots,
        listing_only=args.listing_only,
    )
    log.debug("Configuración: %s", asdict(config))
    run(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
