# F1 multibagger (Yartseva 2025), passo 1: grandezze che mancano nelle matrici.
#  - minimo e massimo delle ultime 252 sedute (prezzo corretto 'a') -> posizione nel range a 12 mesi (variabile "price range"
#    dello studio: (prezzo - minimo 12m) / (massimo 12m - minimo 12m));
#  - per il 2004-2011 (matrice_B, USA con bilanci): rendimento a 36 mesi dai prezzi lunghi (x3), con la regola dei fallimenti
#    dei report precedenti (uscita con ultimo prezzo <25% del massimo dell'anno prima = -100%).
# Nessun credito EODHD.
import pandas as pd, numpy as np, os, sys
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML)
OUT = f'{ML}/f1_out'; os.makedirs(OUT, exist_ok=True)


def rng_at(s, dates):
    """s: Serie del prezzo corretto indicizzata per data. Ritorna DataFrame (date -> pr, lo, hi, px) con le sole sedute <= data."""
    s = s.dropna(); s = s[s > 0]
    if len(s) < 60: return None
    lo = s.rolling(252, min_periods=200).min(); hi = s.rolling(252, min_periods=200).max()
    X = pd.DataFrame({'px': s, 'lo': lo, 'hi': hi})
    X = X.reindex(X.index.union(dates)).ffill().reindex(dates)
    last = s.index[-1]
    X.loc[X.index > last + pd.Timedelta(days=10)] = np.nan
    X['pr'] = (X.px - X.lo) / (X.hi - X.lo)
    X.loc[(X.hi - X.lo) <= 0, 'pr'] = np.nan
    return X


# ------------------------------------------------------------ 2012-2026 (features_v3, prezzi in eod/)
F = pd.read_pickle(f'{ML}/features_v3.pkl')[['t', 'date', 'ex', 'hi52']]
rows = []
for ex, g in F.groupby('ex'):
    E = pd.read_pickle(f'{BW}/eod/{ex}.pkl')
    for t, x in g.groupby('t'):
        code = t.rsplit('.', 1)[0]
        d = E.get(code)
        if d is None or 'a' not in d: continue
        X = rng_at(d['a'], pd.DatetimeIndex(sorted(x.date.unique())))
        if X is None: continue
        X = X.reset_index().rename(columns={'index': 'date'}); X['t'] = t
        rows.append(X[['t', 'date', 'pr', 'lo', 'hi', 'px']])
    del E
    print(ex, 'ok', flush=True)
R = pd.concat(rows)
M = F.merge(R, on=['t', 'date'], how='left')
chk = (M.px / M.hi)
print('copertura price range 2012-26:', M.pr.notna().mean().round(3), ' corr(px/hi, hi52)=', np.corrcoef(chk[chk.notna() & M.hi52.notna()], M.hi52[chk.notna() & M.hi52.notna()])[0, 1].round(3))
M[['t', 'date', 'pr']].to_pickle(f'{OUT}/pr_2012.pkl')

# ------------------------------------------------------------ 2004-2011 (matrice_B, prezzi lunghi USA)
B = pd.read_pickle(f'{ML}/storico5/provaB/matrice_B.pkl')[['t', 'date', 'hi52']]
E = pd.concat([pd.read_pickle(f'{ML}/eod_lungo/US.pkl.gz'), pd.read_pickle(f'{ML}/eod_lungo/US_uscite.pkl.gz')])
E = E.drop_duplicates(['t', 'date']).set_index('date')
G = dict(tuple(E.groupby('t')))
rows = []
for t, x in B.groupby('t'):
    d = G.get(t)
    if d is None: continue
    s = d['a'].sort_index(); s = s[s > 0]
    dates = pd.DatetimeIndex(sorted(x.date.unique()))
    X = rng_at(s, dates)
    if X is None: continue
    # rendimento a 36 mesi (valuta locale, prezzi corretti con dividendi)
    f36 = []
    for dt in dates:
        p0 = s[:dt]
        if not len(p0) or (dt - p0.index[-1]).days > 10: f36.append(np.nan); continue
        p0 = p0.iloc[-1]; end = dt + pd.DateOffset(years=3)
        w = s[(s.index > dt) & (s.index <= end)]
        if not len(w): f36.append(np.nan); continue
        p1 = w.iloc[-1]
        if w.index[-1] < end - pd.Timedelta(days=10):          # uscito prima dei 3 anni
            prev = s[(s.index > w.index[-1] - pd.Timedelta(days=365)) & (s.index <= w.index[-1])]
            if p1 < 0.25 * prev.max(): p1 = 0.0                   # trattato come fallimento
        f36.append(p1 / p0 - 1)
    X['f36'] = f36
    X = X.reset_index().rename(columns={'index': 'date'}); X['t'] = t
    rows.append(X[['t', 'date', 'pr', 'f36']])
R = pd.concat(rows)
M = B.merge(R, on=['t', 'date'], how='left')
print('copertura price range 2004-11:', M.pr.notna().mean().round(3), ' f36:', M.f36.notna().mean().round(3), ' x3:', (M.f36 >= 2).mean().round(4))
M[['t', 'date', 'pr', 'f36']].to_pickle(f'{OUT}/pr_f36_2004.pkl')
