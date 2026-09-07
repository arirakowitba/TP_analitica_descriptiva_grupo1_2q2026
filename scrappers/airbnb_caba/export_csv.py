"""
ETAPA 3 — Consolidación a CSV.

Une el censo (etapa 1) con las fichas (etapa 2), pivotea los amenities a
columnas booleanas y normaliza el precio.

Salidas:
    airbnb_caba_listings.csv   una fila por anuncio, todo junto
    airbnb_caba_amenities.csv  tabla larga (anuncio x amenity)
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parent

# Umbral de precio por noche (USD) arriba del cual el precio no es creíble.
# Medido en el censo del 2026-09-05: 107 de 11.276 anuncios (0,9%) lo superan,
# con casos de USD 89.000 por noche. Son anfitriones que bloquean el calendario
# poniendo un precio impagable en vez de cerrar las fechas. Airbnb los informa
# así (verificado en el desglose crudo), no es un error de parseo. No se borran:
# se marcan, porque arruinan cualquier promedio.
UMBRAL_PRECIO_NOCHE = 1000

# Pivotear los 2.632 amenities distintos daría un CSV de ~2.700 columnas, y la
# cola larga es inservible: 1.538 aparecen en UN solo anuncio, porque Airbnb
# deja que el anfitrión escriba el detalle ("Horno de inducción de acero
# inoxidable de Samsung", "Shampoo variada"). Se pivotean sólo los que están en
# al menos este porcentaje de los anuncios con ficha; el resto no se pierde,
# queda en airbnb_caba_amenities.csv (tabla larga, completa).
UMBRAL_AMENITY = 0.01   # 1% -> ~163 columnas

# Familias: el mismo concepto viene partido en decenas de títulos
# ("Calefacción", "Calefacción: sistema sin conductos tipo split",
# "Calefacción radiante"). Para analizar sirve el concepto, no el título, así
# que además del pivote se arma un booleano por familia. Las claves se buscan
# como substring sobre el nombre en minúsculas y sin acentos.
FAMILIAS = {
    "fam_aire_acondicionado": ["aire acondicionado"],
    "fam_calefaccion":        ["calefaccion"],
    "fam_agua_caliente":      ["agua caliente"],
    "fam_wifi":               ["wifi"],
    "fam_tv":                 ["televis", "tv "],
    "fam_lavarropas":         ["lavarropas"],
    "fam_secarropas":         ["secarropas"],
    "fam_cocina":             ["cocina", "anafe", "horno", "microondas"],
    "fam_heladera":           ["heladera", "freezer"],
    "fam_lavavajillas":       ["lavavajillas"],
    "fam_balcon_patio":       ["balcon", "patio"],
    "fam_terraza":            ["terraza"],
    "fam_jardin":             ["jardin"],
    "fam_parrilla":           ["parrilla"],
    "fam_pileta":             ["pileta"],
    "fam_gimnasio":           ["gimnasio"],
    "fam_sauna":              ["sauna"],
    "fam_ascensor":           ["ascensor"],
    "fam_estacionamiento":    ["estacionamiento", "cochera"],
    "fam_cochera":            ["cochera", "garage"],
    "fam_losa_radiante":      ["calefaccion radiante", "losa radiante"],
    "fam_camaras_seguridad":  ["camara"],
    "fam_portero":            ["portero"],
    "fam_detector_humo":      ["detector de humo"],
    "fam_detector_co":        ["detector de monoxido"],
    "fam_extintor":           ["extintor", "matafuego"],
    "fam_botiquin":           ["botiquin"],
    "fam_caja_fuerte":        ["caja de seguridad", "caja fuerte"],
    "fam_mascotas":           ["mascotas"],
    "fam_zona_trabajo":       ["zona de trabajo"],
    "fam_vista":              ["vista"],
    "fam_entrada_independiente": ["entrada independiente"],
}

# Columnas que son enteras pero conviven con nulos: pandas las pasa a float y
# el CSV termina con "3.0" y "515277659.0". Int64 (nullable) las deja enteras
# y escribe vacío donde no hay dato.
COLS_ENTERAS = ["capacidad", "capacidad_max", "home_tier", "reviews_visibles",
                "cantidad_fotos_pdp", "radio_ofuscacion_m", "comuna", "host_id",
                "host_reviews", "host_anios", "host_cohosts"]


def read_jsonl(p: Path) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame()
    rows = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return pd.DataFrame(rows)


def escribir_csv(df, path: Path) -> bool:
    """Windows + Excel: si el CSV está abierto, to_csv tira PermissionError y
    se lleva puesta la corrida entera. Avisamos y seguimos."""
    try:
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return True
    except PermissionError:
        print(f"NO pude escribir {path.name}: lo tiene tomado otro programa "
              f"(¿Excel?). Cerralo y volvé a correr el export.")
        return False


def parse_precio(txt):
    """'$ 89 USD' -> (89.0, 'USD') ; '$ 123.456 ARS' -> (123456.0, 'ARS')"""
    if not isinstance(txt, str):
        return None, None
    moneda = None
    for m in ("USD", "ARS", "EUR"):
        if m in txt:
            moneda = m
    nums = re.sub(r"[^\d.,]", "", txt)
    # separador de miles con punto, decimal con coma (formato es-AR)
    nums = nums.replace(".", "").replace(",", ".")
    try:
        return float(nums), moneda
    except ValueError:
        return None, moneda


RE_DORM = re.compile(r"(\d+)\s*dormitorio")
RE_CAMA = re.compile(r"(\d+)\s*cama")
# el "1,5 baños" de Airbnb a veces viene con un espacio suelto ("1 ,5 baños")
RE_BANIO = re.compile(r"(\d+(?:\s*,\s*\d+)?)\s*ba[ñn]o")


def parse_estructura(resumen, detalle):
    """De 'Vivienda alquilada · Buenos Aires · ★4,93 · 1 dormitorio · 2 camas ·
    1 baño' saca dormitorios, camas y baños.

    Dos convenciones de Airbnb que hay que traducir:
    - "Estudio" es monoambiente => 0 dormitorios (no es un dato faltante).
    - "1,5 baños" son 1 baño completo + 1 toilette. El medio baño ES el toilette,
      así que de ese mismo número salen las dos columnas.
    """
    # ojo: los anuncios sin ficha traen NaN, que en Python es truthy,
    # así que un "or \"\"" no alcanza para limpiarlo
    partes = [x for x in (resumen, detalle) if isinstance(x, str)]
    if not partes:
        return None, None, None
    t = " | ".join(partes).lower()
    m = RE_DORM.search(t)
    dorm = int(m.group(1)) if m else (0 if "estudio" in t else None)
    m = RE_CAMA.search(t)
    camas = int(m.group(1)) if m else None
    m = RE_BANIO.search(t)
    banios_tot = float(m.group(1).replace(" ", "").replace(",", ".")) if m else None
    return dorm, camas, banios_tot


def parse_noches(qualifier):
    """Noches de la estadía cotizada.

    Con ventana de 30+ noches Airbnb cambia el formato: en vez de
    "por 5 noches" devuelve "mensual", sin número. Ese precio es del mes
    completo y ya tiene aplicado el descuento por estadía larga.
    """
    if not isinstance(qualifier, str):
        return None
    if "mensual" in qualifier.lower():
        return 30
    m = re.search(r"(\d+)\s*noche", qualifier)
    return int(m.group(1)) if m else None


def parse_regimen(qualifier):
    """'mensual' vs 'por_noche': NO son la misma serie de precios."""
    if not isinstance(qualifier, str):
        return None
    return "mensual" if "mensual" in qualifier.lower() else "por_noche"


# Airbnb mezcla en el mismo listado viviendas y alojamiento comercial. Estas
# listas separan una cosa de la otra; se buscan como substring sobre
# tipo_propiedad en minúsculas y sin acentos.
HOTELERO = ["hotel", "hostel", "bed and breakfast", "casa de huespedes",
            "complejo turistico"]
NO_VIVIENDA = ["casa rodante", "casa flotante", "barco", "granja", "castillo"]

# Qué categorías entran al CSV normalizado. Decidido con el usuario (2026-09-06):
# sólo la unidad completa, que es lo comparable con un portal inmobiliario, donde
# se publica el inmueble entero y no un cuarto. Las 516 habitaciones privadas y
# los 391 alojamientos hoteleros quedan afuera de ese archivo, pero SIGUEN en
# airbnb_caba_listings.csv con su categoría marcada: no se pierde nada.
# Los "Departamento con servicios incluidos entero" (385) cuentan como vivienda:
# son departamentos reales alquilados enteros, el servicio de conserjería no
# cambia eso. Quedan identificables por tipo_propiedad si algún día hay que
# sacarlos.
CATEGORIAS_NORMALIZADO = ["vivienda_entera"]

# Cobertura mínima esperada por columna, con los valores medidos en la corrida
# del 2026-09-06. Existe por una razón concreta: el bug del precio (dos
# typenames, el parser leía uno) dejó el 32% de las filas sin precio y NO tiró
# ningún error. Lo encontré de casualidad mirando un describe(). Si una columna
# cae por debajo de su piso, algo cambió del lado de Airbnb y el dataset está
# peor de lo que parece: mejor enterarse acá que a mitad del análisis.
COBERTURA_MINIMA = {
    "listing_id": 1.00, "latitud": 1.00, "longitud": 1.00,
    "cantidad_fotos": 1.00, "precio_txt": 0.99, "precio_valor": 0.99,
    "precio_por_noche": 0.99, "precio_qualifier": 0.99,
    "barrio": 0.90,          # los nulos legítimos son los anuncios de GBA
    "rating_general": 0.70,  # los nulos legítimos son los anuncios sin reviews
}
# éstas dependen de la etapa 2: sólo se validan si hay fichas
COBERTURA_MINIMA_PDP = {
    "capacidad": 0.95, "host_id": 0.95, "tipo_propiedad": 0.95,
    "dormitorios": 0.95, "banios": 0.95, "fam_wifi": 0.95,
}


def validar(df, hay_fichas: bool) -> bool:
    """Chequea la cobertura contra los pisos esperados. Devuelve False si algo
    está por debajo, e imprime SIEMPRE el detalle de lo que falló."""
    esperado = dict(COBERTURA_MINIMA)
    if hay_fichas:
        esperado.update(COBERTURA_MINIMA_PDP)
    problemas = []
    for col, piso in esperado.items():
        if col not in df.columns:
            problemas.append((col, None, piso))
            continue
        cob = df[col].notna().mean()
        if cob < piso:
            problemas.append((col, cob, piso))
    if not problemas:
        print(f"validación: OK, las {len(esperado)} columnas clave están sobre "
              f"su cobertura mínima")
        return True
    print("!" * 70)
    print("VALIDACION FALLIDA: columnas por debajo de la cobertura esperada.")
    print("Casi siempre significa que Airbnb cambió una estructura y el parser")
    print("está leyendo un campo que ya no existe.")
    for col, cob, piso in problemas:
        real = "NO EXISTE" if cob is None else f"{cob*100:.1f}%"
        print(f"  {col:22} {real:>10}  (mínimo esperado {piso*100:.0f}%)")
    print("El crudo está en pdp_full*.jsonl.gz / search_full*.jsonl.gz:")
    print("arreglá el parser y corré reparse.py, sin re-scrapear.")
    print("!" * 70)
    return False


def categoria_alojamiento(tipo_propiedad, room_type):
    """vivienda_entera | habitacion_en_vivienda | hotelero | no_vivienda |
    sin_clasificar (los anuncios que no llegaron a tener ficha)."""
    if not isinstance(tipo_propiedad, str):
        return "sin_clasificar"
    t = sin_acentos(tipo_propiedad)
    if any(k in t for k in HOTELERO):
        return "hotelero"
    if any(k in t for k in NO_VIVIENDA):
        return "no_vivienda"
    if room_type == "Entire home/apt":
        return "vivienda_entera"
    if room_type in ("Private room", "Shared room"):
        return "habitacion_en_vivienda"
    return "sin_clasificar"


def sin_acentos(s):
    s = (s or "").lower()
    return (s.replace("á", "a").replace("é", "e").replace("í", "i")
             .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))


def slug(s):
    return "am_" + re.sub(r"[^a-z0-9]+", "_", sin_acentos(s)).strip("_")[:40]


# Vocabulario del esquema de portales inmobiliarios (ZonaProp y similares),
# para que los dos datasets se puedan cruzar hablando el mismo idioma. Sólo van
# los campos que Airbnb realmente informa: nada inventado. Los que no existen
# (superficie, expensas, dirección, antigüedad, apto_credito) simplemente no
# están, en vez de aparecer como columnas vacías que confundan.
NORMALIZADO = [
    ("property_id", "listing_id"), ("url", "url"), ("scraped_at_utc", "scraped_at_utc"),
    ("titulo", "titulo"), ("descripcion", "descripcion"),
    ("tipo_propiedad", "tipo_propiedad"), ("room_type", "room_type"),
    ("categoria_alojamiento", "categoria_alojamiento"),
    ("es_vivienda", "es_vivienda"),
    ("acepta_corta_estadia", "acepta_corta_estadia"),
    ("solo_larga_estadia", "solo_larga_estadia"),
    ("acepta_larga_estadia", "acepta_larga_estadia"),
    ("precio_regimen", "precio_regimen"),
    ("moneda", "precio_moneda"), ("precio", "precio_por_noche"),
    ("precio_texto", "precio_txt"), ("precio_sospechoso", "precio_sospechoso"),
    ("barrio", "barrio"), ("barrio_norm", "barrio_norm"), ("comuna", "comuna"),
    ("latitud", "latitud"), ("longitud", "longitud"),
    ("ambientes", "ambientes"), ("dormitorios", "dormitorios"),
    ("banios", "banios"), ("toilettes", "toilettes"), ("camas", "camas"),
    ("capacidad", "capacidad"),
    ("seller_id", "host_id"), ("seller_nombre", "host_nombre"),
    ("seller_superhost", "es_superhost"),
    ("rating", "rating_general"), ("reviews", "reviews_visibles"),
    ("cantidad_imagenes", "cantidad_fotos_pdp"), ("imagen_principal", "foto_principal"),
    ("ascensor", "fam_ascensor"), ("balcon_o_patio", "fam_balcon_patio"),
    ("terraza", "fam_terraza"), ("jardin", "fam_jardin"),
    ("parrilla", "fam_parrilla"), ("pileta", "fam_pileta"),
    ("gimnasio", "fam_gimnasio"), ("sauna", "fam_sauna"),
    ("laundry", "fam_lavarropas"), ("cochera", "fam_cochera"),
    ("camaras_seguridad", "fam_camaras_seguridad"), ("portero", "fam_portero"),
    ("aire_acondicionado", "fam_aire_acondicionado"),
    ("calefaccion", "fam_calefaccion"), ("losa_radiante", "fam_losa_radiante"),
    ("internet", "fam_wifi"), ("vista", "fam_vista"),
    ("zona_trabajo", "fam_zona_trabajo"), ("permite_mascotas", "fam_mascotas"),
]


def escribir_normalizado(df, suf=""):
    if "categoria_alojamiento" in df.columns:
        antes = len(df)
        df = df[df["categoria_alojamiento"].isin(CATEGORIAS_NORMALIZADO)]
        print(f"normalizado: {len(df)} de {antes} filas "
              f"({', '.join(CATEGORIAS_NORMALIZADO)})")
    cols = {dest: df[orig] for dest, orig in NORMALIZADO if orig in df.columns}
    n = pd.DataFrame(cols)
    # constantes: son iguales para todo el dataset, pero el esquema las pide
    # Los valores siguen la convencion del resto del proyecto, verificada contra
    # los CSV de MercadoLibre y Argenprop en data_raw: "Airbnb" con mayuscula
    # como las otras fuentes, y "alquiler temporal" que es exactamente lo que
    # usan meli temporario y el otro scraper de airbnb. Si no, un groupby por
    # tipo_operacion nos deja en un bucket propio.
    n.insert(1, "fuente", "Airbnb")
    n.insert(2, "tipo_operacion", "alquiler temporal")
    n.insert(3, "unidad_precio", "por_noche_2_huespedes_5_noches")
    n["amoblado"] = True          # todo Airbnb lo está
    n["localidad"] = "Ciudad Autónoma de Buenos Aires"
    n["provincia"] = "CABA"
    n["pais"] = "Argentina"
    if escribir_csv(n, OUT / f"airbnb_caba_normalizado{suf}.csv"):
        print(f"airbnb_caba_normalizado{suf}.csv -> {len(n)} filas x {n.shape[1]} columnas")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sufijo", default="",
                    help="serie a exportar (ver scrape_search.py --sufijo)")
    args = ap.parse_args()
    suf = args.sufijo
    search = read_jsonl(OUT / f"search_raw{suf}.jsonl")
    pdp = read_jsonl(OUT / f"pdp_raw{suf}.jsonl")
    amen = read_jsonl(OUT / f"amenities_raw{suf}.jsonl")
    if suf:
        # La ficha es del anuncio, no de la ventana de fechas, así que la serie
        # con sufijo sólo bajó las que faltaban (scrape_pdp.py --reusar-fichas)
        # y el resto está en los archivos base. Hay que leer los dos: si no, el
        # CSV mensual saldría con ficha en el 15% de las filas y todo el resto
        # de las columnas vacío, sin ningún error visible.
        base_pdp = read_jsonl(OUT / "pdp_raw.jsonl")
        base_amen = read_jsonl(OUT / "amenities_raw.jsonl")
        if not base_pdp.empty:
            pdp = pd.concat([base_pdp, pdp], ignore_index=True)
            amen = pd.concat([base_amen, amen], ignore_index=True)
            print(f"fichas: {len(base_pdp)} reusadas de la serie base + "
                  f"las propias de esta serie")
    if suf:
        print(f"Serie: {suf}")

    if search.empty:
        print("No hay search_raw.jsonl. Corré scrape_search.py primero.")
        return

    search = search.drop_duplicates(subset="listing_id", keep="first")
    print(f"censo: {len(search)} anuncios")

    # Cruce entre las dos series. Airbnb no expone el mínimo de noches en la
    # ficha (sale de otra query, PdpAvailabilityCalendar), pero comparar los dos
    # censos lo aproxima sin pedir un solo request más: si un anuncio aparece
    # cotizando 30 noches y NO aparece cotizando 5, es que no acepta estadías
    # cortas. Al revés también sirve: el que está en las dos acepta ambas.
    otra_ruta = OUT / ("search_raw.jsonl" if suf else "search_raw_mensual.jsonl")
    if otra_ruta.exists():
        from airbnb_common import jsonl_ids
        ids_otra = jsonl_ids(otra_ruta)
        en_otra = search["listing_id"].astype(str).isin(ids_otra)
        if suf:   # estamos exportando la serie mensual
            search["acepta_corta_estadia"] = en_otra
            search["solo_larga_estadia"] = ~en_otra
            n = int((~en_otra).sum())
            print(f"cruce con la serie corta: {n} de {len(search)} anuncios "
                  f"({n/len(search)*100:.0f}%) sólo aparecen con ventana mensual "
                  f"=> no aceptan estadías de 5 noches")
        else:     # estamos exportando la serie de 5 noches
            search["acepta_larga_estadia"] = en_otra
            n = int(en_otra.sum())
            print(f"cruce con la serie mensual: {n} de {len(search)} anuncios "
                  f"({n/len(search)*100:.0f}%) también cotizan por mes")

    df = search
    if not pdp.empty:
        pdp = pdp.drop_duplicates(subset="listing_id", keep="last")
        print(f"fichas: {len(pdp)} anuncios")
        df = search.merge(pdp, on="listing_id", how="left", suffixes=("", "_pdp"))

    # precio normalizado
    df[["precio_valor", "precio_moneda"]] = df["precio_txt"].apply(
        lambda t: pd.Series(parse_precio(t))
    )
    df["precio_noches"] = df["precio_qualifier"].apply(parse_noches)
    df["precio_regimen"] = df["precio_qualifier"].apply(parse_regimen)
    df["precio_por_noche"] = df["precio_valor"] / df["precio_noches"]
    df["precio_sospechoso"] = df["precio_por_noche"] > UMBRAL_PRECIO_NOCHE

    # precio de lista (los anuncios con descuento traen originalPrice aparte;
    # precio_valor es el efectivamente cobrado)
    if "precio_original_txt" in df.columns:
        df["precio_original_valor"] = df["precio_original_txt"].apply(
            lambda t: parse_precio(t)[0]
        )
        df["descuento_pct"] = (
            (1 - df["precio_valor"] / df["precio_original_valor"]) * 100
        ).round(1)

    # barrio por coordenadas: Airbnb dejó de devolverlo (ni en la búsqueda ni en
    # la PDP), así que se deduce del GeoJSON oficial de los 48 barrios. Ver
    # barrios.py, incluida la advertencia sobre el desplazamiento de ~150 m.
    try:
        from barrios import barrio_de
        lat = df["latitud"]
        lon = df["longitud"]
        if "latitud_pdp" in df.columns:
            lat = lat.fillna(df["latitud_pdp"])
            lon = lon.fillna(df["longitud_pdp"])
        geo = [barrio_de(a, o) for a, o in zip(lat, lon)]
        df["barrio"] = [g[0] for g in geo]
        df["comuna"] = [g[1] for g in geo]
        fuera = int(df["barrio"].isna().sum())
        print(f"barrio asignado por coordenadas: {len(df) - fuera}/{len(df)}"
              + (f" ({fuera} fuera del polígono de CABA)" if fuera else ""))
    except FileNotFoundError as e:
        print(f"\nSin barrio: {e}")

    # amenities -> columnas booleanas
    if not amen.empty:
        amen = amen.drop_duplicates(subset=["listing_id", "amenity"], keep="last")
        con_ficha = set(amen["listing_id"])
        n_fichas = len(con_ficha)

        # la tabla larga sale COMPLETA, sin recortes: es la que no pierde nada
        escribir_csv(amen, OUT / f"airbnb_caba_amenities{suf}.csv")

        # el pivote, en cambio, se recorta por frecuencia (ver UMBRAL_AMENITY)
        frec = amen.groupby("amenity")["listing_id"].nunique()
        minimo = max(1, int(UMBRAL_AMENITY * n_fichas))
        frecuentes = set(frec[frec >= minimo].index)
        print(f"amenities: {len(frec)} distintos en {n_fichas} anuncios; "
              f"se pivotean {len(frecuentes)} (los que están en >= "
              f"{UMBRAL_AMENITY*100:.0f}%, o sea >= {minimo} anuncios)")

        piv_src = amen[amen["amenity"].isin(frecuentes)].copy()
        piv_src["col"] = piv_src["amenity"].apply(slug)
        piv = (piv_src.pivot_table(index="listing_id", columns="col",
                                   values="disponible", aggfunc="first")
               .reset_index())
        df = df.merge(piv, on="listing_id", how="left")

        # familias agrupadas por palabra clave
        disp = amen[amen["disponible"] == True].copy()
        disp["_norm"] = disp["amenity"].apply(sin_acentos)
        for col, claves in FAMILIAS.items():
            m = disp["_norm"].apply(lambda s: any(k in s for k in claves))
            ids = set(disp.loc[m, "listing_id"])
            # NA (no False) para los anuncios sin ficha: no sabemos qué tienen
            df[col] = pd.Series(
                [(lid in ids) if lid in con_ficha else pd.NA
                 for lid in df["listing_id"]],
                index=df.index, dtype="boolean")
        print(f"familias agrupadas: {len(FAMILIAS)} columnas fam_*")

    # estructura del inmueble: Airbnb no la da como campos, la mete en el
    # resumen ("... · 1 dormitorio · 2 camas · 1 baño"). Cobertura medida sobre
    # las 11.252 fichas: dormitorios 99,9%, baños 99,6%, camas 98,1%.
    if "resumen_titulo" in df.columns:
        est = [parse_estructura(r, d) for r, d in
               zip(df["resumen_titulo"], df.get("detalle_items", df["resumen_titulo"]))]
        df["dormitorios"] = pd.array([e[0] for e in est], dtype="Int64")
        df["camas"] = pd.array([e[1] for e in est], dtype="Int64")
        bt = pd.Series([e[2] for e in est], index=df.index, dtype="Float64")
        df["banios_total"] = bt
        # 2,5 baños = 2 completos + 1 toilette
        df["banios"] = bt.apply(lambda v: pd.NA if pd.isna(v) else int(v)).astype("Int64")
        df["toilettes"] = bt.apply(
            lambda v: pd.NA if pd.isna(v) else int(round((v - int(v)) * 2))).astype("Int64")
        # convención local: monoambiente = 1 ambiente. NO es un dato de Airbnb.
        df["ambientes"] = (df["dormitorios"] + 1).astype("Int64")
        print(f"estructura: dormitorios en {int(df['dormitorios'].notna().sum())}, "
              f"baños en {int(df['banios'].notna().sum())} de {len(df)}")

    # vivienda vs alojamiento comercial
    if "tipo_propiedad" in df.columns:
        df["categoria_alojamiento"] = [
            categoria_alojamiento(a, b)
            for a, b in zip(df["tipo_propiedad"], df["room_type"])
        ]
        df["es_vivienda"] = df["categoria_alojamiento"].isin(
            ["vivienda_entera", "habitacion_en_vivienda"])
        vc = df["categoria_alojamiento"].value_counts()
        print("categoría: " + ", ".join(f"{k}={v}" for k, v in vc.items()))

    for c in COLS_ENTERAS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    # Clave de join entre fuentes. Los nombres del GeoJSON oficial vienen sin
    # tilde ("Nuñez", "San Nicolas") y MercadoLibre los escribe con tilde
    # ("Núñez", "San Nicolás"): matchean exacto 37 de 45 barrios, y normalizados
    # 44. Con esta columna el cruce no depende de como escriba cada portal.
    if "barrio" in df.columns:
        df["barrio_norm"] = df["barrio"].apply(
            lambda b: sin_acentos(b).replace(" ", "_") if isinstance(b, str) else None)

    if escribir_csv(df, OUT / f"airbnb_caba_listings{suf}.csv"):
        print(f"\nairbnb_caba_listings{suf}.csv -> {len(df)} filas x {df.shape[1]} columnas")

    faltantes = [c for c in ("precio_valor", "latitud", "cantidad_fotos")
                 if c in df.columns and df[c].isna().any()]
    if faltantes:
        print("\nOJO, columnas con nulos:")
        for c in faltantes:
            print(f"  {c}: {int(df[c].isna().sum())} de {len(df)}")

    validar(df, hay_fichas=not pdp.empty)

    escribir_normalizado(df, suf)

    for c in ("barrio", "comuna", "tipo_propiedad", "room_type"):
        if c in df.columns:
            print(f"\nTop {c}:")
            print(df[c].value_counts().head(8).to_string())


if __name__ == "__main__":
    main()
