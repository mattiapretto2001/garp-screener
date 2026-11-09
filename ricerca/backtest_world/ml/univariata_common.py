# univariata_common: funzioni condivise dell'analisi univariata (IC di rango, AUC, quintili) sulla matrice features_v3.
# Solo periodo di sviluppo 2012-2026 (la matrice parte dal 31/12/2011): l'holdout 2000-2011 non viene mai letto.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
OUT = f'{HERE}/uni_out'; os.makedirs(OUT, exist_ok=True)
REG4 = ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia']          # gruppi che contano per la regola "solida"
PERS = list(fv3.PER3)
# targets principali (relativi alla regione): a) rango del rendimento a 12m, b) top 5%, c) peggiori 20%; piu' crash -50% assoluto
TGT = {'rk': 'rk12_reg', 'top5': 'top5_reg', 'bot20': 'bot20_reg', 'crash': 'crash50'}
TGT_MAIN = ['rk', 'top5', 'bot20']


def load_dev():
    F = fv3.load()
    assert F.date.min() >= pd.Timestamp('2011-12-31')            # niente holdout 2000-2011
    F = F[F.rk12_reg.notna()].copy()                               # date con target a 12 mesi (fino al 30/09/2025)
    F['xs12w'] = fv3.winsor(F, ['xs12_reg'], 0.01)['xs12_reg']     # eccesso tagliato all'1-99% per data (per le medie)
    return F


def pct_rank(X, cols, keys):
    """rango percentile (rank-0.5)/n dentro keys, solo valori presenti"""
    g = X.groupby(keys, observed=True)[cols]
    return (g.rank(method='average') - 0.5) / g.transform('count')


def group_stat(x, y, g, kind, min_n=30, min_pos=3, G=None):
    """statistica per gruppo g: kind='ic' -> correlazione di Pearson (fra ranghi = Spearman);
    kind='auc' -> media del rango fra y=1 meno media fra y=0 (= AUC - 0,5). Ritorna Series indicizzata dai codici di g."""
    m = np.isfinite(x) & np.isfinite(y)
    x, y, g = x[m], y[m], g[m]
    if G is None: G = int(g.max()) + 1 if len(g) else 0
    n = np.bincount(g, minlength=G).astype(float)
    if kind == 'ic':
        sx, sy = np.bincount(g, x, G), np.bincount(g, y, G)
        sxx, syy, sxy = np.bincount(g, x * x, G), np.bincount(g, y * y, G), np.bincount(g, x * y, G)
        with np.errstate(all='ignore'):
            cov = sxy / n - sx * sy / n ** 2
            vx, vy = sxx / n - (sx / n) ** 2, syy / n - (sy / n) ** 2
            r = cov / np.sqrt(vx * vy)
        r[(n < min_n) | (vx < 1e-9) | (vy < 1e-9)] = np.nan          # variabile costante nel gruppo: niente IC
        return r
    npos = np.bincount(g, y, G); nneg = n - npos
    sp = np.bincount(g, x * y, G); sn = np.bincount(g, x * (1 - y), G)
    with np.errstate(all='ignore'):
        d = sp / npos - sn / nneg
    d[(n < min_n) | (npos < min_pos) | (nneg < min_pos)] = np.nan
    return d


def holm(p):
    p = np.asarray(p, float); o = np.argsort(p); m = len(p); adj = np.empty(m)
    run = 0
    for i, k in enumerate(o):
        run = max(run, min(1.0, (m - i) * p[k])); adj[k] = run
    return adj


def bh(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p); q = np.empty(m); prev = 1.0
    for i in range(m - 1, -1, -1):
        k = o[i]; prev = min(prev, p[k] * m / (i + 1)); q[k] = prev
    return q
