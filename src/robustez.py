"""Inferencia exploratoria reproducible. La unidad territorial nunca se replica por aviso.

Los intervalos son bootstrap de las unidades observadas, no intervalos de una
muestra probabilística del mercado. Las permutaciones requieren intercambiabilidad;
la dependencia espacial se diagnostica por separado y limita esa interpretación.
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.linalg import subspace_angles
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler, RobustScaler
from statsmodels.stats.multitest import multipletests

SEED = 2026


def bh(values):
    """BH conserva posiciones y no convierte contrastes no estimables en rechazos."""
    p = np.asarray(values, dtype=float)
    result = np.full(p.shape, np.nan)
    valid = np.isfinite(p)
    if valid.any():
        result[valid] = multipletests(p[valid], method="fdr_bh")[1]
    return result


def _residual_rank(a, controls):
    design = np.column_stack([np.ones(len(a)), controls])
    return a - design @ np.linalg.lstsq(design, a, rcond=None)[0]


def _corr(x, y, controls):
    a, b = stats.rankdata(x), stats.rankdata(y)
    if controls.shape[1]:
        ranked = np.column_stack([stats.rankdata(v) for v in controls.T])
        a, b = _residual_rank(a, ranked), _residual_rank(b, ranked)
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def association(x, y, controls=None, n_boot=999, n_perm=1999, seed=SEED):
    """Spearman o correlación parcial de rangos, IC pareado, permutación y LOO.

    Con controles, permuta residuos de rangos de Y y vuelve a residualizarlos
    (Freedman–Lane aproximado). Controles, familia y dirección deben fijarse antes
    de interpretar p. No corrige automáticamente autocorrelación espacial.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    c = np.empty((len(x), 0)) if controls is None else np.asarray(controls, float).reshape(len(x), -1)
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(c).all(axis=1)
    x, y, c = x[valid], y[valid], c[valid]
    n = len(x)
    empty = dict(n=n, rho=np.nan, lo=np.nan, hi=np.nan, p_perm=np.nan,
                 loo_min=np.nan, loo_max=np.nan, fraccion_boot_signo=np.nan)
    if n < max(8, c.shape[1] + 5):
        return empty
    observed = _corr(x, y, c)
    if not np.isfinite(observed):
        return empty
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        ix = rng.integers(0, n, n)
        boots.append(_corr(x[ix], y[ix], c[ix]))
    boots = np.asarray(boots)
    boots = boots[np.isfinite(boots)]
    a, b = stats.rankdata(x), stats.rankdata(y)
    ranked = np.column_stack([stats.rankdata(v) for v in c.T]) if c.shape[1] else c
    ar, br = _residual_rank(a, ranked), _residual_rank(b, ranked)
    null = []
    for _ in range(n_perm):
        bp = _residual_rank(rng.permutation(br), ranked)
        null.append(np.corrcoef(ar, bp)[0, 1])
    null = np.asarray(null)
    p = (1 + np.sum(np.abs(null) >= abs(observed) - 1e-12)) / (n_perm + 1)
    loo = [_corr(np.delete(x, i), np.delete(y, i), np.delete(c, i, axis=0)) for i in range(n)]
    lo, hi = np.quantile(boots, [.025, .975]) if len(boots) else [np.nan, np.nan]
    return dict(n=n, rho=observed, lo=lo, hi=hi, p_perm=p,
                loo_min=np.nanmin(loo), loo_max=np.nanmax(loo),
                fraccion_boot_signo=np.mean(np.sign(boots) == np.sign(observed)))


def moran(values, coordinates, k=3, n_perm=1999, seed=SEED):
    """Moran I con k vecinos simetrizados y pesos normalizados por fila.

    Coordenadas planas locales o lon/lat escaladas. El p es bilateral alrededor
    de E[I]=-1/(n-1); no es una prueba causal ni corrige otros p-valores.
    """
    x, coords = np.asarray(values, float), np.asarray(coordinates, float)
    valid = np.isfinite(x) & np.isfinite(coords).all(axis=1)
    x, coords = x[valid], coords[valid]
    n = len(x)
    if n < 5 or np.std(x) < 1e-12:
        return dict(n=n, I=np.nan, esperado=np.nan, p_perm=np.nan)
    dist = ((coords[:, None] - coords[None, :]) ** 2).sum(axis=2)
    np.fill_diagonal(dist, np.inf)
    w = np.zeros((n, n))
    for i in range(n):
        w[i, np.argsort(dist[i])[:min(k, n - 1)]] = 1
    w = np.maximum(w, w.T)
    w /= w.sum(axis=1, keepdims=True)
    z = x - x.mean()
    def statistic(v):
        return n / w.sum() * (v @ w @ v) / (v @ v)
    observed, expected = statistic(z), -1 / (n - 1)
    rng = np.random.default_rng(seed)
    null = np.array([statistic(rng.permutation(z)) for _ in range(n_perm)])
    p = (1 + np.sum(np.abs(null - expected) >= abs(observed - expected))) / (n_perm + 1)
    return dict(n=n, I=observed, esperado=expected, p_perm=p)


def two_groups(a, b, n_boot=999, seed=SEED):
    """Diferencia de medianas A-B, Cliff, Mann–Whitney, KS y Brown–Forsythe.

    Solo para grupos definidos externamente, con una observación por unidad.
    El mínimo de 5 impide inferencia asintótica sobre clusters singleton.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    out = dict(n_a=len(a), n_b=len(b), diferencia_mediana=np.nan, lo=np.nan, hi=np.nan,
               cliff=np.nan, p_mw=np.nan, p_ks=np.nan, p_brown_forsythe=np.nan)
    if min(len(a), len(b)) < 5:
        return out
    rng = np.random.default_rng(seed)
    boot = [np.median(rng.choice(a, len(a))) - np.median(rng.choice(b, len(b))) for _ in range(n_boot)]
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided", method="asymptotic")
    out.update(diferencia_mediana=np.median(a)-np.median(b), lo=np.quantile(boot, .025),
               hi=np.quantile(boot, .975), cliff=2*u/(len(a)*len(b))-1, p_mw=p,
               p_ks=stats.ks_2samp(a, b).pvalue,
               p_brown_forsythe=stats.levene(a, b, center="median").pvalue)
    return out


def transform_urban(frame, log=True, robust=False):
    x = frame.to_numpy(dtype=float).copy()
    if log:
        for j, col in enumerate(frame.columns):
            if str(col).endswith("_km2"):
                x[:, j] = np.log1p(np.maximum(x[:, j], 0))
    if not np.isfinite(x).all():
        raise ValueError("La validación urbana requiere casos completos finitos.")
    scaler = RobustScaler() if robust else StandardScaler()
    return scaler.fit_transform(x), scaler


def pca_bootstrap(frame, n_boot=299, seed=SEED):
    """Alinea componentes por asignación y signo; también mide ángulo del subespacio.

    Reajusta escalado en cada bootstrap. Inestabilidad de ejes próximos puede
    coexistir con estabilidad del subespacio; no se interpreta signo absoluto.
    """
    x, _ = transform_urban(frame)
    p = x.shape[1]
    reference = PCA().fit(x)
    r = min(3, p)
    rng = np.random.default_rng(seed)
    weights, variance, angles = [], [], []
    for _ in range(n_boot):
        ix = rng.integers(0, len(frame), len(frame))
        xb, _ = transform_urban(frame.iloc[ix])
        model = PCA().fit(xb)
        # Match todos los ejes, permitiendo intercambios de orden.
        row, col = linear_sum_assignment(-abs(reference.components_ @ model.components_.T))
        aligned = model.components_[col[np.argsort(row)]].copy()
        signs = np.sign(np.sum(aligned * reference.components_, axis=1))
        aligned *= np.where(signs == 0, 1, signs)[:, None]
        weights.append(aligned[:r])
        variance.append(model.explained_variance_ratio_[:r])
        angles.append(np.degrees(subspace_angles(reference.components_[:r].T, model.components_[:r].T)).max())
    weights = np.asarray(weights)
    rows = []
    for pc in range(r):
        for j, name in enumerate(frame.columns):
            vals = weights[:, pc, j]
            rows.append(dict(componente=f"PC{pc+1}", variable=name,
                             peso=reference.components_[pc, j], lo=np.quantile(vals, .025),
                             hi=np.quantile(vals, .975),
                             signo_estable=np.mean(np.sign(vals) == np.sign(reference.components_[pc, j]))))
    return pd.DataFrame(rows), pd.DataFrame(variance, columns=[f"PC{i+1}" for i in range(r)]), np.asarray(angles)


def cluster_sensitivity(frame, reference_labels, n_pc, k, seed=SEED):
    """Reajusta el pipeline completo ante escalado, transformación y exclusión de PM."""
    rows = []
    for name, mask, log, robust, dimensions in [
        ("referencia", np.ones(len(frame), bool), True, False, n_pc),
        ("sin_Puerto_Madero", np.asarray(frame.index != "Puerto Madero"), True, False, n_pc),
        ("sin_log", np.ones(len(frame), bool), False, False, n_pc),
        ("escalado_robusto", np.ones(len(frame), bool), True, True, n_pc),
        ("solo_plano_2PC", np.ones(len(frame), bool), True, False, 2),
        ("todos_componentes", np.ones(len(frame), bool), True, False, frame.shape[1]),
    ]:
        x, _ = transform_urban(frame.loc[mask], log=log, robust=robust)
        z = PCA(n_components=min(dimensions, x.shape[1])).fit_transform(x)
        labels = KMeans(n_clusters=k, n_init=50, random_state=seed).fit_predict(z)
        ward = AgglomerativeClustering(n_clusters=k).fit_predict(z)
        rows.append(dict(escenario=name, n=len(z), k=k, componentes=z.shape[1], grupo_menor=np.bincount(labels).min(),
                         silueta=silhouette_score(z, labels),
                         ari_referencia=adjusted_rand_score(np.asarray(reference_labels)[mask], labels),
                         ari_ward=adjusted_rand_score(labels, ward)))
    return pd.DataFrame(rows)


def territorial_loo(frame, targets, comunas, k_values=(2, 3), seed=SEED):
    """Predicción territorial LOO: PCA, escalado y clusters se aprenden sin el barrio test.

    Predice log(1+y) por mediana de entrenamiento. Comuna sin soporte usa mediana
    global y registra fallback. Objetivos son suplementarios, no entran al PCA.
    No se ajustan k ni umbrales con estos errores de evaluación.
    """
    records = []
    raw = frame.to_numpy(float).copy()
    for j, col in enumerate(frame.columns):
        if str(col).endswith("_km2"):
            raw[:, j] = np.log1p(raw[:, j].clip(min=0))
    comunas = np.asarray(comunas)
    for i in range(len(frame)):
        mask = np.arange(len(frame)) != i
        scaler = StandardScaler().fit(raw[mask])
        pca = PCA().fit(scaler.transform(raw[mask]))
        n_pc = min(5, np.searchsorted(pca.explained_variance_ratio_.cumsum(), .8)+1)
        train = pca.transform(scaler.transform(raw[mask]))[:, :n_pc]
        test = pca.transform(scaler.transform(raw[[i]]))[:, :n_pc]
        partitions = {}
        for k in k_values:
            km = KMeans(n_clusters=k, n_init=20, random_state=seed).fit(train)
            partitions[f"cluster_k{k}"] = km.labels_ == km.predict(test)[0]
        partitions["comuna"] = comunas[mask] == comunas[i]
        partitions["global"] = np.ones(mask.sum(), bool)
        for target in targets:
            values = np.log1p(targets[target].to_numpy(float))
            if not np.isfinite(values[i]):
                continue
            observed = values[mask]
            valid = np.isfinite(observed)
            for model, group in partitions.items():
                support = valid & group
                fallback = support.sum() == 0
                selected = observed[valid] if fallback else observed[support]
                pred = np.median(selected)
                records.append(dict(barrio=frame.index[i], objetivo=target, modelo=model,
                                    observado=values[i], predicho=pred,
                                    error_abs=abs(values[i]-pred), soporte=int(support.sum()),
                                    fallback_global=fallback))
    return pd.DataFrame(records)


def paired_error(a, b, n_boot=1999, seed=SEED):
    """Diferencia pareada de MAE, IC bootstrap de barrios y Wilcoxon exploratorio."""
    delta = np.asarray(a, float) - np.asarray(b, float)
    delta = delta[np.isfinite(delta)]
    rng = np.random.default_rng(seed)
    boots = [rng.choice(delta, len(delta)).mean() for _ in range(n_boot)]
    p = stats.wilcoxon(delta).pvalue if np.any(abs(delta) > 1e-12) else 1.
    return dict(n=len(delta), delta_mae=delta.mean(), lo=np.quantile(boots,.025),
                hi=np.quantile(boots,.975), p_wilcoxon=p)
