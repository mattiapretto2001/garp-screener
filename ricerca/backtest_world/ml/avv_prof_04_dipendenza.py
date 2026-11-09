# avv_prof_04 (verifica avversariale): (a) rotazione trimestrale del Q5 e costo implicito; (b) quanto sono indipendenti i 5 profili
# (correlazione fra le serie trimestrali Q5-U, sovrapposizione dei titoli nel Q5); (c) t con piu' ritardi; (d) test congiunto.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
O2 = f'{HERE}/avv_prof_out'
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
D, Q5set, IC = {}, {}, {}
for k in PNAME:
    s = SC[k]['M0'].astype(float); X = B.loc[s.index]
    q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5); U = X.groupby('date').r_eur.mean()
    r5 = X[q == 5].groupby('date').r_eur.mean().reindex(U.index); D[k] = r5 - U
    S5 = X[q == 5].groupby('date').t.apply(set); Q5set[k] = S5
    to = [1 - len(S5.iloc[i] & S5.iloc[i - 1]) / len(S5.iloc[i]) for i in range(1, len(S5))]
    Zr = s.groupby(X.date).rank(pct=True).to_frame('s'); ic = ic_matrix(Zr, X.rk12_reg, X.date)['s']; IC[k] = ic
    print(f'{k}: rotazione media Q5 per trimestre {np.mean(to):.0%} -> costo ~{np.mean(to) * 2 * COST * 4:.1%}/anno a 0,5% per lato;'
          f' t IC NW4 {nwt(ic, 4):.2f}, NW8 {nwt(ic, 8):.2f}, NW12 {nwt(ic, 12):.2f}; t Q5-U NW0 {nwt(D[k], 0):.2f} NW4 {nwt(D[k], 4):.2f}')
Dd = pd.DataFrame(D); print('\ncorrelazione fra profili delle serie trimestrali Q5-U'); print(Dd.corr().round(2).to_string())
print('\ncorrelazione fra profili delle serie IC'); print(pd.DataFrame(IC).corr().round(2).to_string())
# sovrapposizione dei Q5: quota di titoli del Q5 di A che sono anche nel Q5 di B (media sulle date)
K = list(PNAME); O = pd.DataFrame(index=K, columns=K, dtype=float)
for a in K:
    for b in K:
        O.loc[a, b] = np.mean([len(Q5set[a][d] & Q5set[b].get(d, set())) / len(Q5set[a][d]) for d in Q5set[a].index])
print('\nquota del Q5 di riga presente nel Q5 di colonna'); print(O.round(2).to_string())
# test congiunto: media delle 5 serie Q5-U (portafoglio equipesato dei 5 Q5 contro i 5 universi)
avg = Dd.mean(axis=1); print(f'\nmedia dei 5 profili: Q5-U aritmetico {avg.mean() * 4:.3f}/anno, t NW4 {nwt(avg, 4):.2f}; IC medio t NW4 {nwt(pd.DataFrame(IC).mean(axis=1), 4):.2f}')
for p, (a, b) in list(OOSP.items())[:3]:
    m = (avg.index.year >= a) & (avg.index.year <= b); print(p, round(avg[m].mean() * 4, 3), 'su', m.sum(), 'trimestri; t', round(nwt(avg[m], 2), 2))
Dd.to_csv(f'{O2}/04_q5u_trimestrali.csv')
