# avv_ml_03: robustezza dei portafogli citati in R_ml.md (GBM top30 >=2Mld GARP, Logit due lati top30 >=2Mld GARP, decili)
# varianti: base (riproduzione), senza 2025-26, rendimenti tagliati al 99deg percentile per data (anche nel riferimento),
# costo 1%, senza Asia (universo e riferimento), solo USA, e confronto con la Ridge a penalita' estesa.
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
M = mc.load(); P = pd.read_pickle(f'{mc.OUT}/wf_pred.pkl'); M = M.loc[P.index].join(P)
R2 = pd.read_pickle(f'{mc.HERE}/avv_ml_out/ridge_bordo_pred.pkl'); M = M.join(R2)
APR = [v for v in mc.GLOBAL if fv3.DIRECTION.get(v, 0) != 0]; M['apr'] = M[mc.xcols(APR)].mean(axis=1)
M = M[M.gbm_rk.notna() & (M.date <= mc.LAST_PORT_DATE)].copy()
M['due_lati_lin'] = M.groupby('date').lin_t5.rank(pct=True) + M.groupby('date').lin_b20.rank(pct=True, ascending=False)
M['due_lati_gbm'] = M.groupby('date').gbm_t5.rank(pct=True) + M.groupby('date').gbm_b20.rank(pct=True, ascending=False)
M['big'] = (M.mcap_usd >= 2e9) & ~M.excl_sector
q99 = M.groupby('date').r_eur.transform(lambda s: s.quantile(0.99))
M['r_cap'] = M.r_eur.clip(upper=q99)
SEL = {'GBM rango top30 GARP': ('gbm_rk', 'top30big'), 'Ridge rango top30 GARP': ('lin_rk', 'top30big'),
       'Ridge 1e8 top30 GARP': ('r1e8', 'top30big'), 'Logit due lati top30 GARP': ('due_lati_lin', 'top30big'),
       'GBM due lati top30 GARP': ('due_lati_gbm', 'top30big'), 'A priori top30 GARP': ('apr', 'top30big'),
       'GBM rango decile': ('gbm_rk', 'dec'), 'A priori decile': ('apr', 'dec'), 'GBM eccez decile': ('gbm_t5', 'dec')}
def run(D, cost=0.005, rcol='r_eur'):
    D = D.copy(); D['r_eur'] = D[rcol]; dates = sorted(D.date.unique())
    uni = D.groupby('date').r_eur.mean(); ub = D[D.big].groupby('date').r_eur.mean()
    res = {}
    for nm, (c, kind) in SEL.items():
        D['_s'] = D[c]
        if kind == 'top30big': f = lambda g: g[g.big].nlargest(30, '_s'); b = ub
        else: f = lambda g: g[g._s >= g._s.quantile(0.9)]; b = uni
        pf = mc.port(D, f, dates, cost); st = mc.pstats(pf, b)
        res[nm] = (st['diff'] * 100, st['t'])
    return res
VAR = {'base': (M, 0.005, 'r_eur'), 'senza 2025-26': (M[M.date < '2025-01-01'], 0.005, 'r_eur'),
       'rend. tagliati 99%': (M, 0.005, 'r_cap'), 'costo 1%': (M, 0.01, 'r_eur'),
       'senza Asia': (M[M.reg_rob != 'Asia'], 0.005, 'r_eur'), 'solo USA': (M[M.reg == 'USA'], 0.005, 'r_eur'),
       'senza 2020': (M[M.date.dt.year != 2020], 0.005, 'r_eur')}
out = {}
for k, (D, c, r) in VAR.items():
    res = run(D, c, r); out[k] = {n: f'{d:+.1f} ({t:.1f})' for n, (d, t) in res.items()}; print(k, 'fatto', flush=True)
T = pd.DataFrame(out); T.to_csv(f'{mc.HERE}/avv_ml_out/portafogli_robustezza.csv')
pd.set_option('display.width', 250); print(T.to_string())
