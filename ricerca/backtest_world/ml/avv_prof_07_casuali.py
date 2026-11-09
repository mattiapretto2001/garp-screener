# avv_prof_07 (verifica avversariale): dove si colloca M0 fra punteggi costruiti a caso (fuori campione 2015-2026)?
#  A) 200 sottoinsiemi a caso di 18 variabili fra le 73 con direzione a priori, segno a priori (stessa ricetta di M0, scelta casuale)
#  B) 200 punteggi con le stesse variabili di M0 ma segni a caso (distribuzione "nulla" che tiene conto dei fattori del periodo)
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
O2 = f'{HERE}/avv_prof_out'
B = pd.read_pickle(f'{OUT}/base.pkl')
TECH = ['fin_age_d', 'n_est4', 'logmcap', 'log_adv', 'ind_n']
ALL = [c for c in fv3.PREDICTORS if c not in TECH and fv3.DIRECTION.get(c, 0) != 0]
cg = lambda r: (1 + r).prod() ** (4 / len(r)) - 1
rng = np.random.default_rng(7); rows = []
for k in PNAME:
    Z = pd.read_pickle(f'{OUT}/Z_{k}.pkl'); X = B.loc[Z.index]; oos = (X.date.dt.year >= 2015).values; Z, X = Z[oos], X[oos]
    U = X.groupby('date').r_eur.mean(); cu = cg(U); d = X.date.values
    Zc = (Z[ALL] - 0.5).astype('float32')
    v = X.rk12_reg.notna().values; y = X.rk12_reg.groupby(X.date).rank()  # per IC rapido: Spearman per data

    def ev(s):
        s = pd.Series(s, index=X.index); p = s.groupby(X.date).rank(pct=True)
        r5 = X.r_eur[p > 0.8].groupby(X.date[p > 0.8]).mean().reindex(U.index)
        D = pd.DataFrame({'p': p[v], 'y': y[v], 'd': X.date[v]})
        ic = D.groupby('d').apply(lambda g: np.corrcoef(g.p, g.y)[0, 1]).mean()
        return cg(r5) - cu, ic
    m0 = ev(Zc[CAND[k]].mean(axis=1).values)
    A = [ev(Zc[list(rng.choice(ALL, len(CAND[k]), replace=False))].mean(axis=1).values) for _ in range(200)]
    sg = Zc[CAND[k]].values
    Bn = [ev((sg * rng.choice([-1, 1], len(CAND[k]))).mean(axis=1)) for _ in range(200)]
    A, Bn = np.array(A), np.array(Bn)
    rows.append(dict(profilo=k, M0_Q5U=m0[0], M0_IC=m0[1],
                     A_Q5U_mediana=np.median(A[:, 0]), A_Q5U_quota_positivi=(A[:, 0] > 0).mean(), A_pct_M0_Q5U=(A[:, 0] < m0[0]).mean(),
                     A_IC_mediana=np.median(A[:, 1]), A_pct_M0_IC=(A[:, 1] < m0[1]).mean(),
                     B_Q5U_p95=np.quantile(Bn[:, 0], 0.95), B_pct_M0_Q5U=(Bn[:, 0] < m0[0]).mean(), B_IC_p95=np.quantile(Bn[:, 1], 0.95), B_pct_M0_IC=(Bn[:, 1] < m0[1]).mean()))
    print(pd.Series(rows[-1]).to_string(), flush=True)
R = pd.DataFrame(rows); R.to_csv(f'{O2}/07_punteggi_casuali.csv', index=False)
pd.set_option('display.width', 250); print(R.round(3).to_string(index=False))
