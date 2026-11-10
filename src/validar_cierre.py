"""Verifica mart y cifras de tarjetas contra avisos; escribe evidencia de control."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def verificar(data=None):
    data = Path(data or ROOT / 'data/processed')
    base = pd.read_csv(data / 'df_publicaciones_enriquecidas_v1.csv', low_memory=False)
    fact = pd.read_csv(data / 'dashboard_mart/fact_publicacion.csv', low_memory=False)
    assert len(fact) == len(base), 'El mart altera la cantidad de avisos'
    keys = ['fuente_norm', 'id_publicacion', 'tipo_operacion_norm']
    assert not fact.duplicated(keys).any(), 'Clave de aviso duplicada'
    merged = base.merge(fact, on=keys, suffixes=('_base', '_mart'), validate='one_to_one')
    rows = []
    for op, variable, clean in [
        ('venta', 'precio_m2_usd', 'precio_m2_dashboard'),
        ('alquiler', 'precio_m2_usd', 'precio_m2_dashboard'),
        ('venta', 'precio_venta_usd', 'precio_venta_dashboard'),
        ('alquiler', 'precio_mensual_usd', 'precio_mensual_dashboard'),
    ]:
        expected = merged[f'{variable}_base'].where(
            merged.tipo_operacion_norm.eq(op) & merged.en_alcance_territorial_base & ~merged[f'{variable}_fuera_rango_flag_base'])
        actual = merged[clean].where(merged.tipo_operacion_norm.eq(op))
        assert np.allclose(expected, actual, equal_nan=True), (op, variable)
        rows.append(dict(operacion=op, variable=variable, n=int(actual.count()),
            mediana=float(actual.median()), regla='Mediana sobre avisos normalizados no marcados fuera de rango'))
    summary = pd.DataFrame(rows)
    summary.to_csv(data / 'reports/control_tarjetas_dashboard.csv', index=False)
    # La normalización debe preservar USD y convertir solo ARS con el MEP del aviso.
    portal = base.fuente_norm.ne('airbnb')
    converted = base.precio.where(base.moneda_norm.eq('USD'),
        (base.precio / base.tc_mep).where(base.moneda_norm.eq('ARS')))
    for operation, variable in [('venta','precio_venta_usd'), ('alquiler','precio_mensual_usd'),
                                ('alquiler_temporal','precio_mensual_usd')]:
        use = portal & base.tipo_operacion_norm.eq(operation)
        assert np.allclose(base.loc[use,variable], converted.loc[use], equal_nan=True), 'Regla moneda inconsistente'
    unknown = portal & ~base.moneda_norm.isin(['ARS','USD'])
    assert base.loc[unknown,['precio_venta_usd','precio_mensual_usd']].isna().all().all()
    # Mismo universo de oferta que los KPIs, sin contar las filas de las listas como avisos.
    scoped = fact[fact.en_alcance_territorial]
    kpis = pd.read_csv(data / 'kpis_barrio_v1.csv').set_index('barrio_oficial')
    for operation in ['venta','alquiler','alquiler_temporal']:
        counts = scoped[scoped.tipo_operacion_norm.eq(operation)].groupby('barrio_oficial').size()
        assert counts.reindex(kpis.index,fill_value=0).eq(kpis['n_'+operation]).all(), operation
    surface_rows = []
    for operation in ['venta','alquiler']:
        group = scoped[scoped.tipo_operacion_norm.eq(operation) & scoped.precio_m2_dashboard.notna()]
        surface_rows.append(dict(operacion=operation,n_precio=len(group),
            n_scatter=int(group.superficie_dashboard_m2.notna().sum()),
            n_sin_superficie_visual=int(group.superficie_dashboard_m2.isna().sum()),
            regla='Scatter: superficie valida entre 10 y 2000 m2; tarjeta sin recorte visual'))
    pd.DataFrame(surface_rows).to_csv(data / 'reports/control_superficies_dashboard.csv',index=False)
    lists = pd.read_csv(data / 'reports/listas_operativas_comunas.csv')
    rent = base[base.en_alcance_territorial & base.tipo_operacion_norm.eq('alquiler')
                & ~base.precio_m2_usd_fuera_rango_flag & base.precio_m2_usd.gt(0)]
    expected = rent.groupby('comuna_oficial').precio_m2_usd.agg(['median','count'])
    compared = lists.merge(expected,left_on='comuna',right_index=True,validate='many_to_one')
    assert np.allclose(compared.mediana_alquiler_usd_m2_mes,compared['median'])
    assert compared.n_precio.eq(compared['count']).all()
    gaps = pd.read_csv(data / 'reports/brechas_monitoreo.csv')
    for source, metric in [('airbnb','brecha_airbnb_vs_permanente_pct'),
                           ('mercado_libre','brecha_meli_temporario_vs_permanente_pct')]:
        actual = gaps[gaps.fuente_temporario.eq(source)].set_index('barrio_oficial').brecha_pct
        assert np.allclose(actual.reindex(kpis.index),kpis[metric],equal_nan=True), metric
    return summary


if __name__ == '__main__':
    print(verificar().to_string(index=False))
