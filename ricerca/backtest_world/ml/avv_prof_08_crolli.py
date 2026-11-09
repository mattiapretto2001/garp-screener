# avv_prof_08 (verifica avversariale): (a) i crolli evitati dal decimo migliore di M0 sono solo "bassa volatilita'"? confronto con un punteggio
# di sola volatilita' e di sole 3 variabili di prezzo; (b) Q5-U senza il 2022 (anno della rotazione verso la qualita').
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl')
cg = lambda r: (1 + r).prod() ** (4 / len(r)) - 1
for k in PNAME:
    Z = pd.read_pickle(f'{OUT}/Z_{k}.pkl'); X = B.loc[Z.index]; oos = (X.date.dt.year >= 2015).values; Z, X = Z[oos], X[oos]
    v = X.crash50.notna(); out = []
    for nm, cols in [('M0', CAND[k]), ('solo vol1y', ['vol1y']), ('prezzo 3', ['mom12_1', 'hi52', 'vol1y'])]:
        s = (Z[cols] - 0.5).mean(axis=1) + np.random.default_rng(0).normal(0, 1e-6, len(Z))
        p = s.groupby(X.date).rank(pct=True)
        out.append(f'{nm}: crolli d10 {X.crash50[v & (p >= 0.9)].mean():.3f} disastri d10 {X.bot20_reg[v & (p >= 0.9)].mean():.3f} eccez. d10 {X.top5_reg[v & (p >= 0.9)].mean():.3f}')
    s = (Z[CAND[k]] - 0.5).mean(axis=1); q = s.groupby(X.date).rank(pct=True); U = X.groupby('date').r_eur.mean()
    r5 = X[q > 0.8].groupby('date').r_eur.mean().reindex(U.index); m = U.index.year != 2022
    print(k, f'profilo crolli {X.crash50[v].mean():.3f} |', ' | '.join(out), f'| Q5-U senza 2022: {(cg(r5[m]) - cg(U[m])) * 100:.1f} (con: {(cg(r5) - cg(U)) * 100:.1f})')
