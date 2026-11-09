# avv_ml_01: verifica avversariale di R_ml.md - riproduzione dei numeri chiave e controlli di robustezza sul rango/code
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
O = f'{mc.HERE}/avv_ml_out'; os.makedirs(O, exist_ok=True)
M = mc.load(); P = pd.read_pickle(f'{mc.OUT}/wf_pred.pkl')
APR = [v for v in mc.GLOBAL if fv3.DIRECTION.get(v, 0) != 0]
print('n variabili a priori', len(APR))
M['apr'] = M[mc.xcols(APR)].mean(axis=1)
M = M.join(P)
L = M[M.rk12_reg.notna()]
T = L[L.gbm_rk.notna()]
def ic(D, c, tc='rk12_reg'): return mc.ic_by_date(D[c].values, D[tc].values, D.date.values)
def auc(D, c, tc): return mc.auc_by_date(D[c].values, D[tc].values, D.date.values)
def fmt(s, base=0): return f'{s.mean():+.4f} (t {fv3.nw_t(s - base, 4):.2f}, n {len(s)})'
print('--- riproduzione')
for c in ['gbm_rk', 'gbm1_rk', 'lin_rk', 'apr']: print('IC', c, fmt(ic(T, c)))
for c in ['gbm_c50', 'lin_c50']: print('AUC crolli', c, fmt(auc(T, c, 'crash50'), 0.5))
for c in ['gbm_t5', 'lin_t5']: print('AUC ecc', c, fmt(auc(T, c, 'top5_reg'), 0.5))
d = auc(T, 'gbm_c50', 'crash50') - auc(T, 'lin_c50', 'crash50'); print('gbm-lin crolli', fmt(d))
d = ic(T, 'lin_rk') - ic(T, 'apr'); print('lin-apr rango', fmt(d))
print('--- crolli gbm-lin senza Asia / senza 2025 / solo USA')
for nm, m in [('senza Asia', T.reg_rob != 'Asia'), ('senza Asia ed Europa', ~T.reg_rob.isin(['Asia', 'Europa'])),
              ('senza 2025', T.date.dt.year < 2025), ('solo USA', T.reg == 'USA')]:
    D = T[m]; d = auc(D, 'gbm_c50', 'crash50') - auc(D, 'lin_c50', 'crash50'); print(nm, fmt(d))
print('--- a priori: robustezza')
for nm, m in [('tutto 2016-25', np.ones(len(T), bool)), ('senza 2025-26', T.date.dt.year < 2025), ('senza 2020', T.date.dt.year != 2020),
              ('senza 2022-26', T.date < '2021-12-31'), ('senza Asia', T.reg_rob != 'Asia'), ('solo USA grandi', T.reg_rob == 'USA grandi')]:
    D = T[m]; s = ic(D, 'apr'); dl = ic(D, 'lin_rk'); print(nm, 'apr', fmt(s), '| apr-lin', fmt(s - dl))
# 2012-2015: il punteggio a priori non e' stimato, quindi si puo' valutare anche prima del 2016 (anni di sviluppo, non holdout)
E = L[L.date < '2016-01-01']; s = ic(E, 'apr'); print('apr 2012-2015 (mai usato per i test)', fmt(s)); print(s.groupby(s.index.year).mean().round(3).to_dict())
# per anno, tutte le date 2012-2025
s = ic(L, 'apr'); print('apr per anno 2012-2025:', s.groupby(s.index.year).mean().round(3).to_dict(), 'media', fmt(s))
# senza volatilita'/prezzo; controllando volatilita' e taglia
APR_noP = [v for v in APR if mc.FAM[v] != 'PREZZO']
APR_novol = [v for v in APR if v != 'vol1y']
L2 = T.copy()
L2['apr_noP'] = L2[mc.xcols(APR_noP)].mean(axis=1); L2['apr_novol'] = L2[mc.xcols(APR_novol)].mean(axis=1)
for c in ['apr_noP', 'apr_novol', 'z_vol1y']: print('IC', c, fmt(ic(L2, c)))
# IC parziale: residuo del punteggio rispetto a vol1y e logmcap, data per data
def resid(g, c, ctrl):
    X = g[ctrl].fillna(0).values; X = np.c_[np.ones(len(X)), X]; y = g[c].values
    ok = np.isfinite(y); b = np.linalg.lstsq(X[ok], y[ok], rcond=None)[0]; return pd.Series(y - X @ b, index=g.index)
L2['zlm'] = L2.groupby(['date', 'reg']).mcap_usd.rank(pct=True)
L2['apr_res'] = L2.groupby('date', group_keys=False).apply(lambda g: resid(g, 'apr', ['z_vol1y', 'zlm']))
L2['lin_res'] = L2.groupby('date', group_keys=False).apply(lambda g: resid(g, 'lin_rk', ['z_vol1y', 'zlm']))
for c in ['apr_res', 'lin_res']: print('IC netto di volatilita e taglia', c, fmt(ic(L2, c)))
print('--- concordanza dei segni a priori con l IC univariato')
rows = []
for v in APR:
    s1 = ic(L[L.date < '2016-01-01'], 'z_' + v); s2 = ic(L[L.date >= '2016-01-01'], 'z_' + v)
    rows.append(dict(var=v, fam=mc.FAM[v], ic_1215=s1.mean(), ic_1625=s2.mean(), t_1625=fv3.nw_t(s2, 4)))
S = pd.DataFrame(rows).set_index('var'); S.to_csv(f'{O}/segni_apriori.csv')
print('segni concordi (IC>0 con segno a priori): 2012-15', (S.ic_1215 > 0).sum(), 'su', len(S), '| 2016-25', (S.ic_1625 > 0).sum())
print('con |t|>2 e segno contrario 2016-25:', S[(S.t_1625 < -2)].index.tolist())
print('con |t|>2 e segno concorde 2016-25:', S[(S.t_1625 > 2)].index.tolist())
