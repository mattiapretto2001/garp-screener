# avv_ml_02: la griglia della Ridge si ferma a 1e6 e la scelta cade sul bordo in 6-7 anni su 11.
# Stima walk-forward (stessi split di ml_01) di: Ridge con penalita' 1e7/1e8, limite "penalita' infinita" (pesi = covarianze
# univariate X'y), "segni stimati, pesi uguali" (segno dell'IC univariato sulla finestra di stima). Confronto con lin e apr.
import sys, os, numpy as np, pandas as pd
from sklearn.linear_model import Ridge
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
M = mc.load(); P = pd.read_pickle(f'{mc.OUT}/wf_pred.pkl'); M = M.join(P[['lin_rk', 'gbm_rk']])
APR = [v for v in mc.GLOBAL if fv3.DIRECTION.get(v, 0) != 0]
M['apr'] = M[mc.xcols(APR)].mean(axis=1)
X = mc.xcols(mc.GLOBAL); dates = sorted(M.date.unique())
C = pd.read_csv(f'{mc.OUT}/wf_choices.csv'); print('penalita Ridge scelte (rango):', C[C.target == 'rk'].lin_pen.value_counts().to_dict())
out = {c: pd.Series(np.nan, index=M.index) for c in ['r1e7', 'r1e8', 'xty', 'sgn_eq', 'xty_apr']}
for y, train, test in fv3.walk_forward_splits(dates, 2016, 4):
    Tt = M[M.date.isin(train) & M.rk12_reg.notna()]; S = M[M.date.isin(test)]
    Xt = Tt[X].fillna(0).values; yt = Tt.rk12_reg.values - Tt.rk12_reg.mean(); XS = S[X].fillna(0).values
    for a, nm in [(1e7, 'r1e7'), (1e8, 'r1e8')]:
        out[nm].loc[S.index] = Ridge(alpha=a).fit(Xt, yt).predict(XS)
    w = Xt.T @ yt / len(yt); out['xty'].loc[S.index] = XS @ w
    out['sgn_eq'].loc[S.index] = S[X].mul(np.sign(w)).mean(axis=1).values
    # solo le 62 variabili con segno a priori, segno stimato
    ia = [X.index('z_' + v) for v in APR]; out['xty_apr'].loc[S.index] = S[[X[i] for i in ia]].mul(np.sign(w[ia])).mean(axis=1).values
    agree = (np.sign(w[ia]) > 0).mean(); print(y, 'quota segni stimati = segni a priori: %.2f' % agree)
for k, v in out.items(): M[k] = v
T = M[M.gbm_rk.notna() & M.rk12_reg.notna()]
def ic(D, c): return mc.ic_by_date(D[c].values, D.rk12_reg.values, D.date.values)
base = ic(T, 'lin_rk'); ap = ic(T, 'apr')
for c in ['lin_rk', 'r1e7', 'r1e8', 'xty', 'sgn_eq', 'xty_apr', 'apr']:
    s = ic(T, c); per = [s[[mc.perlab(d) == p for d in s.index]].mean() for p in mc.PERS]
    print(f'{c:8s} IC {s.mean():+.4f} t {fv3.nw_t(s, 4):.2f} | per periodo', np.round(per, 3), f'| meno apr {(s - ap).mean():+.4f} t {fv3.nw_t(s - ap, 4):.2f}')
M[['r1e7', 'r1e8', 'xty', 'sgn_eq', 'xty_apr']].to_pickle(f'{mc.HERE}/avv_ml_out/ridge_bordo_pred.pkl')
