# avv_ml_04: t piu' prudenti. (1) solo date non sovrapposte (un trimestre all'anno -> rendimenti a 12 mesi disgiunti),
# per ciascuno dei 4 trimestri dell'anno; (2) t sulle medie annue (10 anni). (3) segno di neg_eq sui crolli.
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
M = mc.load(); P = pd.read_pickle(f'{mc.OUT}/wf_pred.pkl'); M = M.join(P)
R2 = pd.read_pickle(f'{mc.HERE}/avv_ml_out/ridge_bordo_pred.pkl'); M = M.join(R2[['r1e8', 'sgn_eq']])
APR = [v for v in mc.GLOBAL if fv3.DIRECTION.get(v, 0) != 0]; M['apr'] = M[mc.xcols(APR)].mean(axis=1)
T = M[M.gbm_rk.notna() & M.rk12_reg.notna()]
def ic(c): return mc.ic_by_date(T[c].values, T.rk12_reg.values, T.date.values)
def auc(c, tc): return mc.auc_by_date(T[c].values, T[tc].values, T.date.values)
SER = {'IC apr': ic('apr'), 'IC gbm': ic('gbm_rk'), 'IC lin': ic('lin_rk'), 'IC apr - lin': ic('apr') - ic('lin_rk'),
       'IC apr - Ridge 1e8': ic('apr') - ic('r1e8'), 'IC apr - segni stimati': ic('apr') - ic('sgn_eq'),
       'AUC crolli gbm - lin': auc('gbm_c50', 'crash50') - auc('lin_c50', 'crash50'),
       'AUC ecc gbm1 - lin': auc('gbm1_t5', 'top5_reg') - auc('lin_t5', 'top5_reg')}
def tsimple(x): x = np.asarray(x, float); x = x[np.isfinite(x)]; return x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
rows = []
for nm, s in SER.items():
    r = dict(serie=nm, media=s.mean(), t_NW4=fv3.nw_t(s, 4))
    for q in [3, 6, 9, 12]:
        sq = s[s.index.month == q]; r[f't_solo_mese{q}'] = tsimple(sq); r['n_nonsovr'] = len(sq)
    ya = s.groupby(s.index.year).mean(); r['t_medie_annue'] = tsimple(ya); r['anni_pos'] = f'{(ya > 0).sum()}/{len(ya)}'
    rows.append(r)
R = pd.DataFrame(rows); R.to_csv(f'{mc.HERE}/avv_ml_out/t_conservativi.csv', index=False)
pd.set_option('display.width', 250); print(R.round(3).to_string())
F = pd.read_pickle(f'{mc.HERE}/features_v3.pkl')[['date', 'reg', 'neg_eq', 'crash50', 'bot20_reg', 'mcap_usd']]
F = F[F.crash50.notna()]
print('crolli per patrimonio negativo:'); print(F.groupby(['reg', 'neg_eq'])[['crash50', 'bot20_reg']].mean().round(3).unstack())
print('mcap mediana (M$) per neg_eq:', (F.groupby('neg_eq').mcap_usd.median() / 1e6).round(0).to_dict())
