"""Diagnóstico y sensibilidad de H3, manteniendo venta y alquiler separados."""
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import het_breuschpagan
from .robustez import bh

FORMULA = "lpm2 ~ dm + lsup + C(amb_cat) + C(barrio_oficial) + C(fuente_norm)"


def sample(base):
    keep = (base["fuente_norm"].ne("airbnb") & base["coords_en_caba"].eq(True)
            & base["precio_m2_usd"].gt(0) & ~base["precio_m2_usd_fuera_rango_flag"]
            & base["superficie_ref_m2"].gt(0) & base["ambientes_ref"].notna()
            & base["tipo_operacion_norm"].isin(["venta", "alquiler"]))
    d = base.loc[keep].copy()
    d["lpm2"] = np.log(d["precio_m2_usd"])
    d["lsup"] = np.log(d["superficie_ref_m2"])
    d["amb_cat"] = d["ambientes_ref"].clip(upper=5).astype(int).astype(str)
    d["dm"] = d["dist_transporte_masivo_m"] / 100
    return d.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["lpm2", "lsup", "dm", "barrio_oficial", "fuente_norm"])


def fit(d, formula=FORMULA):
    model = smf.ols(formula, d, missing="raise")
    return model.fit(cov_type="cluster", cov_kwds={
        "groups": d["barrio_oficial"].to_numpy(), "use_correction": True}, use_t=True)


def model_audit(base):
    """Mismos filtros iniciales, escenarios declarados, SE agrupados y t con G-1.

    BP y JB son diagnósticos auxiliares bajo supuestos iid, no la inferencia
    principal. RESET usa la misma agrupación territorial que el modelo base.
    Cook identifica influencia condicional, no errores para borrar del dataset.
    """
    d = sample(base)
    sensitivity, diagnostics, influence, residuals, tests, curves = [], [], [], [], [], []
    for operation, data in d.groupby("tipo_operacion_norm"):
        data = data.reset_index(drop=True)
        fitted = fit(data)
        # Influencia interna OLS evita el costo y supuestos de reestimar n modelos.
        ordinary = fitted.model.fit()
        infl = ordinary.get_influence()
        cook = infl.cooks_distance[0]
        leverage = infl.hat_matrix_diag
        top = np.argsort(cook)[-10:][::-1]
        for ix in top:
            influence.append(dict(operacion=operation, id_publicacion=data.iloc[ix]["id_publicacion"],
                                  barrio=data.iloc[ix]["barrio_oficial"], cook=cook[ix],
                                  leverage=leverage[ix]))
        rng = np.random.default_rng(2026)
        ix_plot = np.sort(rng.choice(len(data), min(5000, len(data)), replace=False))
        residuals.append(pd.DataFrame({"operacion":operation,
            "ajustado_log": np.asarray(fitted.fittedvalues)[ix_plot],
            "residuo_log":np.asarray(fitted.resid)[ix_plot],
            "barrio":data.iloc[ix_plot]["barrio_oficial"].to_numpy()}))
        bp = het_breuschpagan(fitted.resid, fitted.model.exog)
        jb = stats.jarque_bera(fitted.resid)
        diagnostics.append(dict(operacion=operation, n=len(data), barrios=data.barrio_oficial.nunique(),
                                r2_ajustado=fitted.rsquared_adj, AIC=fitted.aic, BIC=fitted.bic, p_bp_iid=bp[1],
                                p_jb_iid=jb.pvalue, max_leverage=leverage.max(),
                                casos_cook_mayor_4n=int((cook > 4/len(data)).sum())))
        # RESET agrupado: potencias de predicción residualizadas mediante diseño ampliado.
        fitted_z = (np.asarray(fitted.fittedvalues)-fitted.fittedvalues.mean()) / fitted.fittedvalues.std()
        augmented = np.column_stack([fitted.model.exog, fitted_z**2, fitted_z**3])
        reset = sm.OLS(fitted.model.endog, augmented).fit(cov_type="cluster",
            cov_kwds={"groups": data.barrio_oficial.to_numpy(), "use_correction": True}, use_t=True)
        restriction = np.zeros((2, augmented.shape[1])); restriction[:, -2:] = np.eye(2)
        reset_test = reset.wald_test(restriction, scalar=True, use_f=True)
        tests.append(dict(operacion=operation, test="RESET_agrupado", p=float(reset_test.pvalue),
                          H0="Coeficientes de predicción al cuadrado y cubo iguales a cero"))
        scenarios = {
            "referencia_t_Gmenos1":data,
            "precio_p01_p99":data[data.lpm2.between(*data.lpm2.quantile([.01,.99]))],
            "sin_1pct_Cook":data.loc[cook <= np.quantile(cook,.99)],
            "geocodificacion_directa":data[data.metodo_geo.eq("rest_calle_altura")],
            "sin_Puerto_Madero":data[data.barrio_oficial.ne("Puerto Madero")],
            "solo_Mercado_Libre":data[data.fuente_norm.eq("mercadolibre")],
        }
        # No asumir alias del portal: identificar mayor fuente observada si difiere.
        scenarios["fuente_mayoritaria"] = data[data.fuente_norm.eq(data.fuente_norm.value_counts().index[0])]
        scenarios.pop("solo_Mercado_Libre")
        for name, subset in scenarios.items():
            if subset.barrio_oficial.nunique() < 15 or len(subset) < 100:
                sensitivity.append(dict(operacion=operation, escenario=name, n=len(subset),
                    barrios=subset.barrio_oficial.nunique(), efecto_pct=np.nan,
                    lo=np.nan, hi=np.nan, p=np.nan, estado="soporte insuficiente"))
                continue
            m = fitted if name == "referencia_t_Gmenos1" else fit(subset)
            beta = m.params["dm"]; lo, hi = m.conf_int().loc["dm"]
            sensitivity.append(dict(operacion=operation, escenario=name, n=len(subset),
                barrios=subset.barrio_oficial.nunique(), efecto_pct=100*np.expm1(beta),
                lo=100*np.expm1(lo), hi=100*np.expm1(hi), p=m.pvalues["dm"], estado="estimado"))
        # Contraste de forma funcional, sin seleccionar por significancia.
        nonlinear = fit(data, FORMULA+" + I(dm ** 2)")
        tests.append(dict(operacion=operation, test="curvatura_distancia", p=nonlinear.pvalues["I(dm ** 2)"],
                          H0="Coeficiente cuadrático de distancia igual a cero"))
        log_distance = fit(data, FORMULA.replace("~ dm +", "~ np.log1p(dm) +"))
        for name, alternative in [("cuadratico", nonlinear), ("log_distancia", log_distance)]:
            # RESET agrupado también en alternativas; no seleccionar por el menor p.
            pred = np.asarray(alternative.fittedvalues)
            pred = (pred-pred.mean())/pred.std()
            design = np.column_stack([alternative.model.exog, pred**2, pred**3])
            checked = sm.OLS(alternative.model.endog, design).fit(cov_type="cluster",
                cov_kwds={"groups":data.barrio_oficial.to_numpy(),"use_correction":True},use_t=True)
            restriction = np.zeros((2,design.shape[1]));restriction[:,-2:]=np.eye(2)
            reset_p=float(checked.wald_test(restriction,scalar=True,use_f=True).pvalue)
            tests.append(dict(operacion=operation,test="RESET_"+name,p=reset_p,
                              H0="Potencias de valores ajustados no agregan explicación condicional"))
            for percentile in [.25,.5,.75]:
                start=float(data.dm.quantile(percentile))
                contrast=np.zeros(len(alternative.params))
                if name=="cuadratico":
                    contrast[alternative.params.index.get_loc("dm")]=1
                    contrast[alternative.params.index.get_loc("I(dm ** 2)")]=2*start+1
                else:
                    contrast[alternative.params.index.get_loc("np.log1p(dm)")]=np.log((start+2)/(start+1))
                delta=float(contrast@alternative.params)
                se=np.sqrt(max(0,float(contrast@alternative.cov_params()@contrast)))
                critical=stats.t.ppf(.975,data.barrio_oficial.nunique()-1)
                curves.append(dict(operacion=operation,forma=name,percentil_distancia=percentile,
                    distancia_inicial_m=start*100,incremento_m=100,n=len(data),
                    efecto_pct=100*np.expm1(delta),lo=100*np.expm1(delta-critical*se),
                    hi=100*np.expm1(delta+critical*se),r2_ajustado=alternative.rsquared_adj,
                    AIC=alternative.aic,RESET_p=reset_p))
        # Contraste de controles de fuente: estabilidad del coeficiente no prueba ausencia de sesgo.
        terms = [i for i, name in enumerate(fitted.params.index) if name.startswith("C(fuente_norm)")]
        if terms:
            r = np.eye(len(fitted.params))[terms]
            w = fitted.wald_test(r, scalar=True, use_f=True)
            tests.append(dict(operacion=operation,test="fuente_conjunta",p=float(w.pvalue),
                              H0="Coeficientes de fuente iguales a cero, condicionales a controles"))
    sensitivity, tests = pd.DataFrame(sensitivity), pd.DataFrame(tests)
    tests["q_BH"] = bh(tests.p)
    # Los escenarios son sensibilidad, no una familia de descubrimientos independientes.
    return sensitivity, pd.DataFrame(diagnostics), pd.DataFrame(influence), pd.concat(residuals), tests, pd.DataFrame(curves)
