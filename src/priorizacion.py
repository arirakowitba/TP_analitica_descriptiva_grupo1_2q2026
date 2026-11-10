"""Listas de diagnóstico por decisión; no estima déficit ni desplazamiento."""
import numpy as np
import pandas as pd


def listas_operativas(base, comunas, seed=2026):
    rent = base.loc[base.en_alcance_territorial & base.tipo_operacion_norm.eq('alquiler') &
                    base.precio_m2_usd.gt(0) & ~base.precio_m2_usd_fuera_rango_flag].copy()
    table = comunas.set_index('comuna').copy()
    rng = np.random.default_rng(seed)
    rows = []
    for comuna, group in rent.groupby('comuna_oficial'):
        values = group.precio_m2_usd.to_numpy()
        # Bootstrap de avisos, condicionado a la captura; no cubre sesgo de portal.
        boots = [np.median(rng.choice(values, len(values))) for _ in range(999)]
        rows.append(dict(comuna=comuna, mediana_alquiler_usd_m2_mes=np.median(values),
                         n_precio=len(values), ic95_lo=np.quantile(boots, .025),
                         ic95_hi=np.quantile(boots, .975),
                         proporcion_ARS=group.moneda_norm.eq('ARS').mean(),
                         fuentes_precio=group.fuente_norm.nunique()))
    table = table.join(pd.DataFrame(rows).set_index('comuna'))
    table['ratio_airbnb_permanente'] = table.n_airbnb / table.n_alquiler.replace(0, np.nan)
    # Tres decisiones distintas; nunca exigir permanente bajo para monitorear temporario.
    definitions = {
        'monitoreo_temporario': ('airbnb_por_1000_viviendas', False),
        'diagnostico_oferta_permanente': ('alquiler_por_1000_hogares_inquilinos', True),
        'diagnostico_precio': ('mediana_alquiler_usd_m2_mes', False),
    }
    lists, scenarios = [], []
    for decision, (metric, ascending) in definitions.items():
        t = table.dropna(subset=[metric]).copy()
        if decision == 'diagnostico_precio':
            t = t[t.n_precio.ge(30)]
        t = t.sort_values([metric, 'n_alquiler'], ascending=[ascending, False])
        t['decision'] = decision
        t['puesto'] = np.arange(1, len(t) + 1)
        t['indicador_orden'] = metric
        t['precio_alto_P75'] = t.mediana_alquiler_usd_m2_mes.ge(table.mediana_alquiler_usd_m2_mes.quantile(.75))
        t['airbnb_alto_P75'] = t.airbnb_por_1000_viviendas.ge(table.airbnb_por_1000_viviendas.quantile(.75))
        # Sensibilidad: ranking y pertenencia a la cola segun el corte, con cortes y soporte explícitos.
        for minimum in [20, 30, 50, 100]:
            for shock in [-.1, 0, .1]:
                rr = rent.assign(escenario=rent.precio_m2_usd / np.where(rent.moneda_norm.eq('ARS'), 1 + shock, 1))
                med = rr.groupby('comuna_oficial').escenario.agg(['median', 'size'])
                eligible = table.dropna(subset=[metric]).join(med.rename(columns={'median':'precio_escenario','size':'n_escenario'}))
                # Soporte de precio solo condiciona decisiones que usan precio para ordenar.
                if decision == 'diagnostico_precio':
                    eligible = eligible[eligible.n_escenario.ge(minimum)]
                order_metric = 'precio_escenario' if decision == 'diagnostico_precio' else metric
                eligible = eligible.sort_values(order_metric, ascending=ascending)
                for q in [.6, .7, .75, .8, .9]:
                    cut = eligible[order_metric].quantile(1-q if ascending else q)
                    selected = eligible[order_metric].le(cut) if ascending else eligible[order_metric].ge(cut)
                    for rank, (idx, row) in enumerate(eligible.iterrows(), 1):
                        scenarios.append(dict(decision=decision, comuna=idx, minimo=minimum,
                            shock_MEP=shock, cuantil=q, puesto=rank, seleccionada=bool(selected.loc[idx])))
        lists.append(t.reset_index())
    sensitivity = pd.DataFrame(scenarios)
    stability = sensitivity.groupby(['decision','comuna']).agg(
        escenarios=('puesto','size'), puesto_min=('puesto','min'), puesto_max=('puesto','max'),
        fraccion_seleccionada=('seleccionada','mean')).reset_index()
    result = pd.concat(lists, ignore_index=True).merge(stability, on=['decision','comuna'], validate='one_to_one')
    result['incertidumbre_conteos'] = 'Captura no probabilistica: sin IC poblacional; no mide stock ni contratos'
    return result, sensitivity


def brechas_monitoreo(base, barrios, seed=2026):
    """Brecha mensual por ambiente, fuentes separadas y soporte pareado explícito."""
    usable = base.loc[base.en_alcance_territorial & base.precio_mensual_usd.gt(0)
        & ~base.precio_mensual_usd_fuera_rango_flag & base.ambientes_ref.ge(1)].copy()
    usable['mensual_por_ambiente'] = usable.precio_mensual_usd / usable.ambientes_ref
    rng = np.random.default_rng(seed)
    rows = []
    for barrio, group in usable.groupby('barrio_oficial'):
        permanent = group.loc[group.tipo_operacion_norm.eq('alquiler'), 'mensual_por_ambiente'].to_numpy()
        for source in ['airbnb', 'mercado_libre']:
            temporal = group.loc[group.tipo_operacion_norm.eq('alquiler_temporal') & group.fuente_norm.eq(source),
                                 'mensual_por_ambiente'].to_numpy()
            n_p, n_t = len(permanent), len(temporal)
            row = dict(barrio_oficial=barrio, fuente_temporario=source,
                       n_permanente=n_p, n_temporario=n_t,
                       brecha_pct=np.nan, ic95_lo=np.nan, ic95_hi=np.nan,
                       estado='Soporte insuficiente: minimo 30 avisos por lado')
            if min(n_p, n_t) >= 30:
                bootstrap = [100 * (np.median(rng.choice(temporal,n_t)) /
                            np.median(rng.choice(permanent,n_p)) - 1) for _ in range(999)]
                row.update(brecha_pct=100 * (np.median(temporal) / np.median(permanent) - 1),
                    ic95_lo=np.quantile(bootstrap,.025), ic95_hi=np.quantile(bootstrap,.975),
                    estado='IC condicional a captura; productos y gastos distintos, no rentabilidad')
            rows.append(row)
    return pd.DataFrame(rows).merge(barrios[['barrio_oficial','comuna']], on='barrio_oficial', validate='many_to_one')
