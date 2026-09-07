"""
Utilidades compartidas para el scrapeo de Airbnb CABA.

Arquitectura general (por qué esto y no Selenium):
Airbnb sirve el estado inicial de React embebido en el HTML, dentro de
<script id="data-deferred-state-0">. Ahí está el JSON completo de resultados.
Entonces alcanza con requests.get() + json.loads(). No hay navegador, no hay
DOM, no hay clases ofuscadas que se rompan cada dos semanas.
"""
from __future__ import annotations

import base64
import gzip
import json
import random
import re
import time
from pathlib import Path

import requests

API_KEY = "d306zoyjsyarp7ifhu67rjxn52tv0t20"
HOST = "https://www.airbnb.com.ar"
LOCALE = "es-AR"
CURRENCY = "USD"  # cambialo a "ARS" si querés pesos; ver nota en README

DEFERRED_RE = re.compile(
    r'<script id="data-deferred-state-0"[^>]*>(.*?)</script>', re.DOTALL
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class Blocked(Exception):
    """El HTML volvió sin estado embebido: rate limit o desafío de bot."""


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def polite_sleep(base: float = 1.2, jitter: float = 0.8) -> None:
    """Ritmo deliberadamente lento. No lo bajes de 1s."""
    time.sleep(base + random.random() * jitter)


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def unb64(s: str) -> str:
    return base64.b64decode(s).decode()


def listing_id_from_gid(gid: str) -> str | None:
    """'RGVtYW5kU3RheUxpc3Rpbmc6MTIzNA==' -> '1234'"""
    try:
        return unb64(gid).split(":", 1)[1]
    except Exception:
        return None


def make_cursor(items_offset: int) -> str:
    """
    El cursor de paginación NO hay que scrapearlo: es base64 de
    {"section_offset":0,"items_offset":N,"version":1} con N saltando de 18 en 18.
    """
    payload = json.dumps(
        {"section_offset": 0, "items_offset": items_offset, "version": 1},
        separators=(",", ":"),
    )
    return base64.b64encode(payload.encode()).decode()


def get_deferred_state(session: requests.Session, url: str, retries: int = 4) -> dict:
    """GET + extracción del JSON embebido, con backoff exponencial."""
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            last = e
            time.sleep(4 * (2 ** attempt))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            last = f"HTTP {r.status_code}"
            time.sleep(10 * (2 ** attempt))
            continue
        m = DEFERRED_RE.search(r.text)
        if m:
            return json.loads(m.group(1))
        last = f"sin estado embebido (HTTP {r.status_code}, {len(r.text)} bytes)"
        time.sleep(8 * (2 ** attempt))
    raise Blocked(f"{url[:120]}… -> {last}")


def jsonl_gz_append(path: Path, rec: dict) -> None:
    """Guarda la respuesta CRUDA, comprimida.

    ¿Por qué existe esto? Porque los .jsonl guardan el registro ya parseado, y
    cada vez que descubrimos un campo que no estábamos leyendo hay que volver a
    scrapear para recuperarlo. Pasó tres veces en la primera corrida (el precio
    con descuento, los agregados de reviews, el desglose del precio). Con el
    crudo en disco, mejorar el parser es re-parsear en minutos y sin tocar
    Airbnb.

    Formato: gzip multi-miembro, una línea JSON por registro. Cada append abre
    un miembro nuevo; gzip.open() al leer los concatena de forma transparente,
    así que el archivo se lee como un JSONL normal.
    """
    with gzip.open(path, "at", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")


def jsonl_gz_read(path: Path):
    """Itera los registros crudos. Tolera la última línea cortada, que es lo que
    queda si el proceso murió a mitad de un write."""
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def jsonl_append(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def jsonl_ids(path: Path, key: str = "listing_id") -> set[str]:
    """IDs ya guardados, para poder reanudar sin repetir trabajo."""
    seen: set[str] = set()
    if not path.exists():
        return seen
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line).get(key)
            except json.JSONDecodeError:
                continue
            if v:
                seen.add(str(v))
    return seen
