# avv_prof_06 (verifica avversariale): M0 togliendo una variabile alla volta (fuori campione 2015-2026): quanto dipende da singole variabili.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
O2 = f'{HERE}/avv_prof_out'
B = pd.read_pickle(f'{OUT}/base.pkl')
cg = lambda r: (1 + r).prod() ** (4 / len(r)) - 1
rows = []
for k in PNAME:
    Z = pd.read_pickle(f'{OUT}/Z_{k}.pkl'); X = B.loc[Z.index]; oos = (X.date.dt.year >= 2015).values; Z, X = Z[oos], X[oos]
    U = X.groupby('date').r_eur.mean()
    for drop in [None] + CAND[k]:
        cols = [c for c in CAND[k] if c != drop]; s = (Z[cols] - 0.5).mean(axis=1)
        q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
        r5 = X[q == 5].groupby('date').r_eur.mean().reindex(U.index)
        ic = ic_matrix(s.groupby(X.date).rank(pct=True).to_frame('s'), X.rk12_reg, X.date)['s']
        rows.append(dict(profilo=k, tolta=drop or '(nessuna)', IC=ic.mean(), Q5_U=cg(r5) - cg(U), arit=(r5 - U).mean() * 4))
R = pd.DataFrame(rows); R.to_csv(f'{O2}/06_togli_una.csv', index=False)
for k in PNAME:
    x = R[R.profilo == k].set_index('tolta'); b = x.loc['(nessuna)']
    d = (x.drop('(nessuna)')[['IC', 'Q5_U']] - b[['IC', 'Q5_U']]).sort_values('Q5_U')
    print(k, f'base IC {b.IC:.3f} Q5-U {b.Q5_U * 100:.1f}; Q5-U senza una variabile: min {x.Q5_U.min() * 100:.1f} max {x.Q5_U.max() * 100:.1f}; IC min {x.IC.min():.3f} max {x.IC.max():.3f}')
    print('   variabili che, tolte, abbassano di piu il Q5-U:', ', '.join(f'{i} {v * 100:+.1f}' for i, v in d.Q5_U.head(4).items()),
          '| abbassano di piu IC:', ', '.join(f'{i} {v:+.3f}' for i, v in d.IC.sort_values().head(3).items()))
