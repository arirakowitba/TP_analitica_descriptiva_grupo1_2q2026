"""
Asignación de barrio por coordenadas (CABA).

¿Por qué hace falta esto? Airbnb dejó de devolver el barrio (verificado
2026-09-05): en modo mapa —el único que acepta bounding box— el `title` del
resultado viene null, y en modo lista pasó a decir "Departamento en Buenos
Aires", o sea la ciudad. La PDP tampoco lo trae: LOCATION_PDP.subtitle es
"Buenos Aires, Buenos Aires, Argentina" y `address` viene null.

Entonces el barrio se deduce de las coordenadas contra el GeoJSON oficial de
los 48 barrios (data.buenosaires.gob.ar, CRS84 = WGS84 lon/lat). Ray casting
en Python puro: no suma dependencias, todo sigue corriendo con requests+pandas.

LIMITACIÓN, leer antes de usarlo para algo fino: la precisión de la coordenada
no es uniforme. Airbnb declara en mapMarkerRadiusInMeters el radio del círculo
que dibuja en el mapa, y en el censo del 2026-09-06 dio: 0 m en el 52% de los
anuncios (con la coordenada redondeada a 4 decimales, o sea una grilla de ~11 m),
152 m en el 44% y 500 m en el 4%. Para agregar por barrio alcanza en los tres
casos; para algo más fino sólo sirven los de radio 0. Nunca sirve para ubicar
la unidad: no hay calle ni altura.

Uso:
    from barrios import barrio_de
    nombre, comuna = barrio_de(-34.6037, -58.3816)   # -> ('San Nicolas', 1)

Autotest:
    python barrios.py
"""
from __future__ import annotations

import json
from pathlib import Path

GEOJSON = Path(__file__).parent / "barrios_caba.geojson"
FUENTE = ("https://cdn.buenosaires.gob.ar/datosabiertos/datasets/"
          "ministerio-de-educacion/barrios/barrios.geojson")

_cache: list | None = None


def _bbox(anillos):
    xs = [x for anillo in anillos for x, _ in anillo]
    ys = [y for anillo in anillos for _, y in anillo]
    return min(xs), min(ys), max(xs), max(ys)


def load(path: Path = GEOJSON) -> list:
    """[(nombre, comuna, bbox, [polígono...]), ...]; cada polígono es
    [anillo_exterior, agujero, agujero, ...]."""
    global _cache
    if _cache is not None:
        return _cache
    if not path.exists():
        raise FileNotFoundError(
            f"Falta {path.name}. Bajalo de:\n    {FUENTE}\n"
            f"y dejalo en {path.parent}"
        )
    j = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in j.get("features") or []:
        g = f.get("geometry") or {}
        props = f.get("properties") or {}
        tipo = g.get("type")
        if tipo == "Polygon":
            polis = [g["coordinates"]]
        elif tipo == "MultiPolygon":
            polis = g["coordinates"]
        else:
            continue
        anillos = [anillo for poli in polis for anillo in poli]
        out.append((props.get("nombre"), props.get("comuna"),
                    _bbox(anillos), polis))
    _cache = out
    return out


def _en_anillo(x: float, y: float, anillo) -> bool:
    """Ray casting: cuenta cruces de la horizontal que pasa por (x, y)."""
    dentro = False
    n = len(anillo)
    j = n - 1
    for i in range(n):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > y) != (yj > y):
            # x del cruce del segmento (i, j) con la horizontal y
            xcruce = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < xcruce:
                dentro = not dentro
        j = i
    return dentro


def _en_poligono(x: float, y: float, poli) -> bool:
    if not _en_anillo(x, y, poli[0]):
        return False
    # anillos 1..n son agujeros
    return not any(_en_anillo(x, y, agujero) for agujero in poli[1:])


def barrio_de(lat, lon) -> tuple:
    """(nombre, comuna) o (None, None) si el punto cae fuera de CABA."""
    try:
        y, x = float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
    for nombre, comuna, (xmin, ymin, xmax, ymax), polis in load():
        if not (xmin <= x <= xmax and ymin <= y <= ymax):
            continue  # descarte rápido por bounding box
        if any(_en_poligono(x, y, p) for p in polis):
            return nombre, comuna
    return None, None


if __name__ == "__main__":
    casos = [
        (-34.6037, -58.3816, "San Nicolas"),      # Obelisco
        (-34.5875, -58.4300, "Palermo"),          # Plaza Serrano
        (-34.6345, -58.3630, "La Boca"),          # Caminito
        (-34.5885, -58.3930, "Recoleta"),         # Recoleta
        (-34.6208, -58.3730, "San Telmo"),        # Plaza Dorrego
        (-34.6118, -58.3630, "Puerto Madero"),    # Puerto Madero
        (-34.5450, -58.4620, "Nuñez"),            # Nuñez
        (-34.6180, -58.4420, "Caballito"),        # Parque Rivadavia
        (-34.6600, -58.4700, "Villa Lugano"),     # Lugano
        (-34.9000, -58.3000, None),               # fuera de CABA
    ]
    print(f"{len(load())} barrios cargados de {GEOJSON.name}\n")
    ok = 0
    for lat, lon, esperado in casos:
        got, comuna = barrio_de(lat, lon)
        marca = "OK " if got == esperado else "MAL"
        ok += got == esperado
        print(f"  {marca} ({lat}, {lon}) -> {got!r} comuna={comuna} "
              f"| esperado {esperado!r}")
    print(f"\n{ok}/{len(casos)} correctos")
