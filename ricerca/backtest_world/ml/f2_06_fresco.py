# F2 passo 6 (controllo a posteriori, dichiarato): segnale "fresco", evento depositato negli ultimi 30 giorni prima della fine del
# trimestre (invece di 90), per vedere se l'effetto si consuma nei primi mesi. Stesso confronto di f2_05 (caso a parita' di data,
# taglia, volatilita' e distanza dal massimo; t su date annuali non sovrapposte).
import os, numpy as np, pandas as pd
ML = os.path.dirname(os.path.abspath(__file__)); OUT = f'{ML}/f2'
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
SIG = ['ANY', 'C2_30', 'C2_90', 'C3_90', 'BIG1M', 'PCT20', 'CEO100']
U = pd.read_pickle(f'{OUT}/pannello_f2.pkl').drop(columns=SIG)
S = pd.read_pickle(f'{OUT}/segnali_trim_fresh30.pkl')
U = U.merge(S[['t', 'date'] + SIG], on=['t', 'date'], how='left')
for s in SIG: U[s] = U[s].fillna(False).astype(bool)
U['ok12'] = U.f12c.notna(); U['ok36'] = U.f36.notna() & (U.date <= '2022-12-31')
CELL = ['date', 'taglia', 'vq', 'pq']


def t_matched(D, s, tgt, okc, step):
    x = D[D[okc] & D.taglia.notna()].copy()
    x['exp'] = x.groupby(CELL, observed=True)[tgt].transform('mean')
    y = x[x[s]]
    g = y.groupby('date').agg(n=(tgt, 'size'), o=(tgt, 'mean'), e=('exp', 'mean'))
    g = g[g.n >= 5]; dif = g.o - g.e
    dd = sorted(x.date.unique()); idx = {d: i for i, d in enumerate(dd)}
    ts = []
    for off in range(step):
        v = dif[[idx[d] % step == off for d in dif.index]]
        if len(v) >= 3 and v.std() > 0: ts.append(v.mean() / v.std() * np.sqrt(len(v)))
    return y[tgt].mean(), y.exp.mean(), (np.mean(ts) if ts else np.nan)


rows = []
for tg in ['tutte', 'piccole 0,3-2', 'medie 2-15', 'grandi >15']:
    X = U if tg == 'tutte' else U[U.taglia == tg]
    for s in SIG:
        r = dict(taglia=tg, segnale=s, n=int(X[X.ok12][s].sum()))
        for tgt, okc, step in (('W5', 'ok12', 4), ('X3', 'ok36', 12), ('L50', 'ok12', 4)):
            r[tgt], r[tgt + '_casoV'], r[tgt + '_tV'] = t_matched(X, s, tgt, okc, step)
        x = X[X.ok12]; r['ecc_media'] = x[x[s]].ecc.mean(); r['ecc_mediana'] = x[x[s]].ecc.median(); r['ecc_mediana_uni'] = x.ecc.median()
        rows.append(r)
R = pd.DataFrame(rows); R.to_csv(f'{OUT}/tab_fresco30.csv', index=False)
print(R.round(3).to_string())
