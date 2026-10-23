"""Construye el mart dimensional PE3 para el dashboard.

Hechos separados por granularidad; no unir hechos directamente.
La clave natural de publicación se valida y nunca se deduplica silenciosamente.
"""
from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUT = DATA / "dashboard_mart"
OUT.mkdir(parents=True, exist_ok=True)

def load(name):
    p = DATA / name
    if not p.exists():
        raise FileNotFoundError(f"Falta {p}; ejecutar antes el pipeline de datos.")
    return pd.read_csv(p, low_memory=False)

def find(df, options, required=False):
    col = next((x for x in options if x in df.columns), None)
    if required and col is None:
        raise KeyError(f"No existe ninguna de estas columnas: {options}")
    return col

def make_dim(df, natural, key, display=None):
    cols = [natural] + [c for c in (display or []) if c in df.columns and c != natural]
    out = df[cols].drop_duplicates(natural).copy()
    out[natural] = out[natural].fillna("No informado").astype(str)
    out = out.sort_values(natural).reset_index(drop=True)
    out.insert(0, key, np.arange(1, len(out) + 1, dtype="int64"))
    return out

def foreign_key(fact, dim, fact_col, dim_col, key):
    fact[fact_col] = fact[fact_col].fillna("No informado").astype(str)
    return fact.merge(dim[[dim_col, key]], left_on=fact_col, right_on=dim_col,
                      how="left", validate="many_to_one").drop(
                          columns=[dim_col] if dim_col != fact_col else [])

def save(df, name):
    df.to_csv(OUT / f"{name}.csv", index=False)
    return {"tabla": name, "filas": int(len(df)), "columnas": list(df.columns)}

pub = load("df_publicaciones_enriquecidas_v1.csv")
kb = load("kpis_barrio_v1.csv")
kc = load("kpis_comuna_v1.csv")
ctx = load("features_contextuales_barrio_v1.csv")

op_src = find(pub, ["tipo_operacion_norm", "tipo_operacion"], True)
source_src = find(pub, ["fuente_norm", "fuente"], True)
id_src = find(pub, ["id_publicacion", "id", "url"], True)
date_src = find(pub, ["fecha_extraccion", "fecha_publicacion"])
barrio_src = find(pub, ["barrio_oficial", "barrio"])
comuna_src = find(pub, ["comuna"])
type_src = find(pub, ["tipo_propiedad", "tipo_propiedad_norm"])
currency_src = find(pub, ["moneda_norm", "moneda"])
nk = [source_src, id_src, op_src]
dups = pub.duplicated(nk, keep=False)
if dups.any():
    raise ValueError("Duplicada clave natural fuente × publicación × operación; revisar upstream: "
                     + str(pub.loc[dups, nk].head(8).to_dict("records")))

# Dimensiones: valores naturales preservados y surrogate keys para relaciones 1:N.
dims = {}
dims["dim_fuente"] = make_dim(pub, source_src, "fuente_key")
ops = pd.DataFrame({"operacion": pd.concat([
    pub[op_src].dropna().astype(str),
    pd.Series(["alquiler", "alquiler_temporal", "venta", "airbnb"])
], ignore_index=True).drop_duplicates()})
dims["dim_operacion"] = make_dim(ops, "operacion", "operacion_key")
if type_src: dims["dim_tipo_propiedad"] = make_dim(pub, type_src, "tipo_propiedad_key")
if currency_src: dims["dim_moneda"] = make_dim(pub, currency_src, "moneda_key")
if "comuna" in kc:
    dims["dim_comuna"] = make_dim(kc, "comuna", "comuna_key")
if "barrio_oficial" in kb:
    db = make_dim(kb, "barrio_oficial", "barrio_key", ["comuna"])
    if "comuna" in db and "dim_comuna" in dims:
        db["comuna"] = db["comuna"].fillna("No informado").astype(str)
        db = db.merge(dims["dim_comuna"][["comuna", "comuna_key"]], on="comuna",
                      how="left", validate="many_to_one").drop(columns="comuna")
    dims["dim_barrio"] = db

if date_src:
    dates = pd.to_datetime(pub[date_src], errors="coerce").dropna().dt.normalize().drop_duplicates()
    d = pd.DataFrame({"fecha": dates})
    d["fecha_key"] = d.fecha.dt.strftime("%Y%m%d").astype("int64")
    d["anio"] = d.fecha.dt.year
    d["mes"] = d.fecha.dt.month
    d["trimestre"] = d.fecha.dt.quarter
    dims["dim_fecha"] = d[["fecha_key", "fecha", "anio", "mes", "trimestre"]]

# Hecho publicación: oferta capturada; mantener disponibles atributos/precio/moneda originales.
measure_cols = ["precio_usd", "precio_mep_usd", "precio", "superficie_ref_m2",
 "precio_m2_usd", "ambientes_ref", "dormitorios_ref", "banios_ref", "latitud", "longitud",
 "es_geocodificado", "flag_geocodificacion"]
keep = [c for c in [id_src, source_src, op_src, date_src, barrio_src, comuna_src,
                     type_src, currency_src] + measure_cols if c and c in pub]
fp = pub[keep].copy().rename(columns={id_src: "id_publicacion"})
fp["cantidad_publicaciones"] = 1
fp = foreign_key(fp, dims["dim_fuente"], source_src, source_src, "fuente_key")
# La dimensión de operación usa nombre natural estándar; la FK respeta el campo original.
fp = foreign_key(fp, dims["dim_operacion"], op_src, "operacion", "operacion_key")
if type_src:
    fp = foreign_key(fp, dims["dim_tipo_propiedad"], type_src, type_src, "tipo_propiedad_key")
if currency_src:
    fp = foreign_key(fp, dims["dim_moneda"], currency_src, currency_src, "moneda_key")
if barrio_src and "dim_barrio" in dims:
    if barrio_src != "barrio_oficial": fp = fp.rename(columns={barrio_src: "barrio_oficial"})
    fp = foreign_key(fp, dims["dim_barrio"], "barrio_oficial", "barrio_oficial", "barrio_key")
# Para evitar dos rutas de filtro hacia comuna, publicación se relaciona con barrio;
# comuna se deriva por dim_barrio.comuna_key. El agregado comunal usa sus propios hechos.
if date_src and "dim_fecha" in dims:
    fp["fecha"] = pd.to_datetime(fp[date_src], errors="coerce").dt.normalize()
    fp = fp.merge(dims["dim_fecha"][["fecha", "fecha_key"]], on="fecha",
                  how="left", validate="many_to_one")

# Hechos de conteo operación: no replican KPIs ni denominadores por cada categoría.
op_counts = {"alquiler":"n_alquiler", "alquiler_temporal":"n_alquiler_temporal",
             "venta":"n_venta", "airbnb":"n_airbnb"}
def make_operation_fact(source, geo, geo_key, grain):
    records = []
    for label, count_col in op_counts.items():
        if geo in source and count_col in source:
            part = source[[geo, count_col]].rename(columns={count_col: "cantidad_publicaciones"}).copy()
            part["operacion"] = label
            part["grano"] = grain
            records.append(part)
    out = pd.concat(records, ignore_index=True) if records else pd.DataFrame(
        columns=[geo, "cantidad_publicaciones", "operacion", "grano"])
    if len(out):
        out = foreign_key(out, dims["dim_operacion"], "operacion", "operacion", "operacion_key")
        if geo_key in dims:
            out = foreign_key(out, dims[geo_key], geo, geo, "barrio_key" if geo=="barrio_oficial" else "comuna_key")
    return out

fb = make_operation_fact(kb, "barrio_oficial", "dim_barrio", "barrio × corte PE2 × operación")
fc = make_operation_fact(kc, "comuna", "dim_comuna", "comuna × corte PE2 × operación")

# Agregados barriales y comunales permanecen en su grano original, sin expandirlos por operación.
fkb = kb.copy()
if "dim_barrio" in dims:
    fkb = foreign_key(fkb, dims["dim_barrio"], "barrio_oficial", "barrio_oficial", "barrio_key")
market_comuna_cols = ["comuna", "venta_por_1000_viviendas", "alquiler_por_1000_viviendas",
 "airbnb_por_1000_viviendas", "alquiler_por_1000_hogares_inquilinos",
 "publicaciones_por_1000_hab", "airbnb_por_cada_alquiler_permanente"]
fkc = kc[[c for c in market_comuna_cols if c in kc]].drop_duplicates("comuna").copy()
if "dim_comuna" in dims:
    fkc = foreign_key(fkc, dims["dim_comuna"], "comuna", "comuna", "comuna_key")

fctx = ctx.copy()
if "dim_barrio" in dims and "barrio_oficial" in fctx:
    fctx = foreign_key(fctx, dims["dim_barrio"], "barrio_oficial", "barrio_oficial", "barrio_key")

census_cols = ["comuna", "superficie_km2", "poblacion_total", "densidad_hab_km2",
 "poblacion_viv_particulares", "viviendas_total", "viviendas_particulares",
 "viviendas_ocupadas", "viviendas_uso_temporal", "viviendas_uso_oficina",
 "viviendas_en_alquiler_o_venta", "hogares", "viviendas_ocupadas_casa",
 "viviendas_ocupadas_departamento", "hogares_propietarios", "hogares_inquilinos",
 "tamano_medio_hogar", "pct_hogares_inquilinos", "pct_viviendas_departamento",
 "pct_viviendas_uso_temporal", "pct_viviendas_en_alquiler_o_venta"]
fce = kc[[c for c in census_cols if c in kc]].drop_duplicates("comuna").copy()
if "dim_comuna" in dims:
    fce = foreign_key(fce, dims["dim_comuna"], "comuna", "comuna", "comuna_key")
fce["anio_censo"] = 2022

facts = {"fact_publicacion":fp, "fact_barrio_operacion":fb, "fact_kpi_barrio":fkb,
 "fact_comuna_operacion":fc, "fact_kpi_comuna":fkc,
 "fact_contexto_barrio":fctx, "fact_censo_comuna":fce}
grains = {
 "fact_publicacion":"fuente × id_publicacion × operación",
 "fact_barrio_operacion":"barrio × corte PE2 × operación",
 "fact_kpi_barrio":"barrio × corte PE2",
 "fact_comuna_operacion":"comuna × corte PE2 × operación",
 "fact_kpi_comuna":"comuna × corte PE2 (solo indicadores de mercado)",
 "fact_contexto_barrio":"barrio × versión contextual",
 "fact_censo_comuna":"comuna × Censo 2022"
}
manifest = {"version":"pe3_mart_v1",
 "fuentes":["df_publicaciones_enriquecidas_v1.csv","kpis_barrio_v1.csv",
            "kpis_comuna_v1.csv","features_contextuales_barrio_v1.csv"],
 "granos":grains,
 "clave_natural_fact_publicacion":nk,
 "reglas":[
  "No relacionar hechos entre sí; dimensiones filtran hechos con cardinalidad 1:N.",
  "Precios no son aditivos: mostrar mediana/percentiles separados por operación y moneda.",
  "Conteos reflejan publicaciones observadas, no stock habitacional ni contratos.",
  "No inferir tendencias temporales desde una fecha/corte de extracción.",
  "Los denominadores censales permanecen en granularidad comuna.",
  "Las tasas no se promedian entre territorios; usar KPI validado o recomponer cociente."
 ],
 "salidas":[]}
for name, df in dims.items(): manifest["salidas"].append(save(df, name))
for name, df in facts.items():
    if name == "fact_publicacion" and len(df) != len(pub):
        raise AssertionError("Se alteró el número de publicaciones al incorporar dimensiones.")
    manifest["salidas"].append(save(df, name))
(OUT / "data_model.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"salidas":[{"tabla":x["tabla"],"filas":x["filas"]} for x in manifest["salidas"]],
                  "granos":grains}, ensure_ascii=False, indent=2))
