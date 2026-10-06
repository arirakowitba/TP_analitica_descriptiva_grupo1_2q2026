"""Funciones del EDA con fuentes externas: estadísticos, correlaciones con incertidumbre,
modelos con errores agrupados y gráficos reutilizables (mapas por barrio, forest plots)."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import PathPatch
from scipy import stats
import statsmodels.formula.api as smf

TEXTO = '#0b0b0b'
TEXTO_2 = '#52514e'
GRILLA = '#e8e7e3'
# Categórica, primeros tres slots (validados todos contra todos): venta, alquiler, temporario.
COLOR_OPERACION = {'venta': '#2a78d6', 'alquiler': '#eb6834', 'alquiler_temporal': '#1baf7a'}
NOMBRE_OPERACION = {'venta': 'Venta', 'alquiler': 'Alquiler', 'alquiler_temporal': 'Temporario'}
RAMPA_AZUL = ['#e6f0fb', '#b9d4f3', '#7fb0e8', '#3f86d6', '#1f5aa8', '#12386b']
SIN_DATO = '#ececea'


def estilo():
    plt.rcParams.update({
        'figure.dpi': 110, 'savefig.dpi': 110, 'font.size': 9,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.edgecolor': TEXTO_2, 'axes.labelcolor': TEXTO_2, 'axes.titlecolor': TEXTO,
        'xtick.color': TEXTO_2, 'ytick.color': TEXTO_2, 'axes.titlesize': 10,
        'axes.titlelocation': 'left', 'axes.grid': True, 'grid.color': GRILLA, 'grid.linewidth': 0.6,
        'axes.axisbelow': True, 'legend.frameon': False,
    })


def describir(serie):
    """Resumen de posición, dispersión y forma de una variable."""
    s = pd.to_numeric(serie, errors='coerce').dropna()
    return pd.Series({'n': len(s), 'media': s.mean(), 'mediana': s.median(), 'desvio': s.std(),
                      'p10': s.quantile(.10), 'p25': s.quantile(.25), 'p75': s.quantile(.75), 'p90': s.quantile(.90),
                      'asimetria': s.skew(), 'cv': s.std() / s.mean() if s.mean() else np.nan})


def spearman_boot(x, y, n_boot=2000, seed=42):
    """Spearman con p-valor e intervalo de confianza del 95% por bootstrap percentil."""
    d = pd.DataFrame({'x': x, 'y': y}).dropna()
    if len(d) < 5:
        return {'rho': np.nan, 'lo': np.nan, 'hi': np.nan, 'p': np.nan, 'n': len(d)}
    rho, p = stats.spearmanr(d['x'], d['y'])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    xs, ys = d['x'].to_numpy(), d['y'].to_numpy()
    boots = np.array([stats.spearmanr(xs[i], ys[i])[0] for i in idx])
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    return {'rho': rho, 'lo': lo, 'hi': hi, 'p': p, 'n': len(d)}


def tabla_spearman(df, y, variables, etiquetas=None, **kw):
    """Spearman de `y` contra cada variable de `variables`."""
    filas = []
    for v in variables:
        r = spearman_boot(df[v], df[y], **kw)
        r['variable'] = (etiquetas or {}).get(v, v)
        filas.append(r)
    return pd.DataFrame(filas)[['variable', 'rho', 'lo', 'hi', 'p', 'n']]


def ols_cluster(df, formula, cluster):
    """OLS con errores estándar robustos agrupados (los avisos de un mismo barrio no son independientes)."""
    grupos = df[cluster].astype('category').cat.codes
    return smf.ols(formula, df).fit(cov_type='cluster', cov_kwds={'groups': grupos})


def coef_pct(modelo, termino, escala=1.0):
    """Efecto porcentual aproximado (100 x coeficiente de un modelo log-lineal) y su IC95%."""
    b = 100 * modelo.params[termino] * escala
    lo, hi = (100 * modelo.conf_int().loc[termino] * escala).tolist()
    return b, lo, hi, modelo.pvalues[termino]


def forest(ax, tabla, col_etiqueta='variable', col_valor='rho', col_lo='lo', col_hi='hi', color='#2a78d6',
           xlabel='Correlación de Spearman', decimales=2, referencia=0.0):
    """Puntos con intervalo. Relleno si el intervalo excluye la referencia, hueco si la incluye."""
    t = tabla.reset_index(drop=True)
    y = np.arange(len(t))[::-1]
    for yi, (_, r) in zip(y, t.iterrows()):
        sig = (r[col_lo] > referencia) or (r[col_hi] < referencia)
        ax.plot([r[col_lo], r[col_hi]], [yi, yi], color=color, lw=1.6, solid_capstyle='round', zorder=2)
        ax.scatter(r[col_valor], yi, s=46, zorder=3, edgecolor=color, linewidth=1.6,
                   facecolor=color if sig else 'white')
        ax.annotate(f'{r[col_valor]:.{decimales}f}', (r[col_hi], yi), xytext=(6, -3), textcoords='offset points',
                    fontsize=8, color=TEXTO_2)
    ax.axvline(referencia, color=TEXTO_2, lw=0.9, zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels(t[col_etiqueta])
    ax.set_xlabel(xlabel)
    ax.grid(axis='y', visible=False)


def mapa_barrios(ax, barrios, valores, titulo, norm=None, cmap_colores=RAMPA_AZUL, unidad='', fmt='{:,.0f}'):
    """Mapa coroplético de los 48 barrios con una rampa secuencial de un solo tono."""
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list('rampa', cmap_colores)
    v = barrios['barrio_oficial'].map(valores)
    norm = norm or Normalize(vmin=np.nanpercentile(v, 2), vmax=np.nanpercentile(v, 98))
    for (_, b), val in zip(barrios.iterrows(), v):
        color = SIN_DATO if pd.isna(val) else cmap(norm(val))
        for path in b['_paths']:
            ax.add_patch(PathPatch(path, facecolor=color, edgecolor='white', linewidth=0.5))
    todos = np.vstack([p.vertices for paths in barrios['_paths'] for p in paths])
    ax.set_xlim(todos[:, 0].min() - 0.005, todos[:, 0].max() + 0.005)
    ax.set_ylim(todos[:, 1].min() - 0.005, todos[:, 1].max() + 0.005)
    ax.set_aspect(1 / np.cos(np.radians(-34.6)))
    ax.set_axis_off()
    ax.set_title(titulo)
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = plt.colorbar(sm, ax=ax, fraction=0.04, pad=0.01, shrink=0.7)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7, colors=TEXTO_2)
    cb.set_label(unidad, fontsize=8, color=TEXTO_2)


def rotular_extremos(ax, x, y, etiquetas, k=3, prefijo=''):
    """Rotula solo los k puntos más altos y más bajos en cada eje, para evitar superposición."""
    d = pd.DataFrame({'x': np.asarray(x, dtype=float), 'y': np.asarray(y, dtype=float), 'e': list(etiquetas)}).dropna()
    elegidos = set(d.nlargest(k, 'x').index) | set(d.nsmallest(k, 'x').index) \
        | set(d.nlargest(k, 'y').index) | set(d.nsmallest(k, 'y').index)
    for i in elegidos:
        ax.annotate(f'{prefijo}{d.loc[i, "e"]}', (d.loc[i, 'x'], d.loc[i, 'y']), xytext=(4, 3),
                    textcoords='offset points', fontsize=7.5, color=TEXTO_2)
