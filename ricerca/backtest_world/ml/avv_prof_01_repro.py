# avv_prof_01 (verifica avversariale, 07/11): ricalcolo indipendente di M0 (dai ranghi Z, senza scores_oos) e delle misure chiave
# (IC fuori campione, Q5/Q1 contro universo del profilo, decimo migliore). Confronto con i CSV dell'autore.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
O2 = f'{HERE}/avv_prof_out'; os.makedirs(O2, exist_ok=True)
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
rows = []
for k in PNAME:
    Z = pd.read_pickle(f'{OUT}/Z_{k}.pkl')
    m0 = (Z[CAND[k]] - 0.5).mean(axis=1)
    m0 = m0[B.loc[m0.index, 'date'].dt.year >= 2015]
    diff = (m0 - SC[k]['M0'].astype(float).reindex(m0.index)).abs().max()
    X = B.loc[m0.index]
    # IC: correlazione di Spearman per data fra punteggio e rendimento a 12 mesi (indipendente da ic_matrix)
    D = pd.DataFrame({'s': m0, 'y': X.fwd12_eur, 'd': X.date}).dropna()
    ic = D.groupby('d').apply(lambda g: g.s.rank().corr(g.y.rank()))
    q = np.ceil(m0.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
    U = X.groupby('date').r_eur.mean()
    r5 = X[q == 5].groupby('date').r_eur.mean().reindex(U.index); r1 = X[q == 1].groupby('date').r_eur.mean().reindex(U.index)
    cg = lambda r: (1 + r).prod() ** (4 / len(r)) - 1
    v = X.top5_reg.notna(); d10 = m0.groupby(X.date).rank(pct=True) >= 0.9
    rows.append(dict(profilo=k, maxdiff_M0=diff, ic_spearman_fwd12=ic.mean(), t_nw=nwt(ic), Q5_U=cg(r5) - cg(U), Q1_U=cg(r1) - cg(U),
                     Q5_U_arit=(r5 - U).mean() * 4, Q1_U_arit=(r1 - U).mean() * 4, Q5_Q1_arit=(r5 - r1).mean() * 4,
                     crash_d10=X.crash50[v & d10].mean(), crash_prof=X.crash50[v].mean()))
T = pd.DataFrame(rows); pd.set_option('display.width', 250)
print(T.round(4).to_string(index=False)); T.to_csv(f'{O2}/01_repro.csv', index=False)
