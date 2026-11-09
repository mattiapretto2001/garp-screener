# temi_common: funzioni comuni per lo screener dei temi "emergenti" ex ante (industria x data)
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
OUT = f'{HERE}/temi_out'; os.makedirs(OUT, exist_ok=True)
MIN_N = 8                       # industria valida a una data: almeno 8 societa' nell'universo (tutte le regioni)
EXCL_SECT = {'Financial Services', 'Real Estate', 'Financial', 'Financials', 'Other'}   # ricavi non confrontabili: niente temi qui
# nomi di industria in stile GICS/Refinitiv ricondotti a quelli EODHD (solo i casi ovvi); spazi iniziali tolti
IND_MAP = {'Software': 'Software - Application', 'Software & IT Services': 'Software - Application',
           'Pharmaceuticals': 'Drug Manufacturers - General', 'Biotechnology & Medical Research': 'Biotechnology',
           'Healthcare Equipment & Supplies': 'Medical Instruments & Supplies', 'Metals & Mining': 'Other Industrial Metals & Mining',
           'Independent Power and Renewable Electricity Producers': 'Utilities - Independent Power Producers',
           'Electrical Utilities & IPPs': 'Utilities - Independent Power Producers', 'Oil & Gas Related Equipment and Services': 'Oil & Gas Equipment & Services',
           'Oil, Gas & Consumable Fuels': 'Oil & Gas E&P', 'Automobiles & Auto Parts': 'Auto Parts', 'Banks': 'Banks - Diversified',
           'Banking Services': 'Banks - Regional', 'Communications & Networking': 'Communication Equipment', 'Beverages': 'Beverages - Non-Alcoholic',
           'Telecommunications Services': 'Telecom Services', 'Professional Services': 'Consulting Services'}
PER3 = fv3.PER3
nw_t = fv3.nw_t


def norm_ind(s):
    s = s.astype('object').where(s.notna(), None)
    s = s.map(lambda x: x.strip() if isinstance(x, str) else x)
    return s.replace(IND_MAP)


def per3_of(d):
    d = pd.Timestamp(d)
    for p, (a, b) in PER3.items():
        if pd.Timestamp(a) <= d <= pd.Timestamp(b): return p
    return None


def holm(pvals):
    """correzione di Holm: restituisce p corretti"""
    p = np.asarray(pvals, float); n = len(p); o = np.argsort(p); adj = np.empty(n); run = 0
    for i, k in enumerate(o):
        run = max(run, (n - i) * p[k]); adj[k] = min(1, run)
    return adj


def tp(t):
    """p bilaterale approssimato (normale) da un t"""
    from math import erf, sqrt
    return 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2)))) if np.isfinite(t) else np.nan


def portfolio(F, sel, w=None, cost=0.005, start='2011-12-31', end='2026-09-30'):
    """backtest trimestrale a pesi uguali (o w) su r_eur; sel = maschera booleana su F (alla data di formazione).
    costo = cost * somma |delta peso| (acquisti + vendite). Restituisce serie trimestrale netta e turnover."""
    D = sorted(F.date[(F.date >= start) & (F.date <= end)].unique())
    prev = pd.Series(dtype=float); rets = {}; turns = {}
    for d in D:
        m = sel & (F.date == d)
        X = F.loc[m, ['t', 'r_eur']]
        if len(X) == 0: rets[d] = 0.0; wt = pd.Series(dtype=float)
        else:
            wt = pd.Series(1.0 / len(X), index=X.t.values) if w is None else (w[m] / w[m].sum()).set_axis(X.t.values)
            rets[d] = float((wt.values * X.r_eur.fillna(0).values).sum())
        allk = wt.index.union(prev.index)
        tv = (wt.reindex(allk).fillna(0) - prev.reindex(allk).fillna(0)).abs().sum()
        turns[d] = tv; rets[d] -= cost * tv
        # pesi a fine trimestre (deriva) per il turnover successivo
        if len(X): prev = (wt * (1 + X.r_eur.fillna(0).values)); prev = prev / prev.sum() if prev.sum() > 0 else prev
        else: prev = wt
    return pd.Series(rets), pd.Series(turns)


def cagr(q):
    q = pd.Series(q).dropna()
    return (np.prod(1 + q.values)) ** (4 / len(q)) - 1 if len(q) else np.nan


def maxdd(q):
    v = np.cumprod(1 + pd.Series(q).fillna(0).values); return float((v / np.maximum.accumulate(v) - 1).min())
