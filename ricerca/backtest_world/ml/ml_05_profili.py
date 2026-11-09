# ml_05: il guadagno del modello non lineare dentro i sotto-universi dei profili (stesse previsioni mondiali di ml_01,
# valutate solo sulle societa' del sotto-universo alla data, con dati gia' noti alla data).
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
M = mc.load(); P = pd.read_pickle(f'{mc.OUT}/wf_pred.pkl')
M = M.loc[P.index].join(P); M = M[M.gbm_rk.notna() & M.rk12_reg.notna()]
APR = [v for v in mc.GLOBAL if fv3.DIRECTION.get(v, 0) != 0]
M['apr_rk'] = M[mc.xcols(APR)].mean(axis=1); M['apr_t5'] = M.apr_rk; M['apr_b20'] = -M.apr_rk; M['apr_c50'] = -M.apr_rk
SUB = {'Tutte': np.ones(len(M), bool),
       'Settori GARP >=2 Mld$': (~M.excl_sector & (M.mcap_usd >= 2e9)).values,
       'Profittevoli (utile e FCF >0)': ((M.ni_ttm > 0) & (M.fcf_ttm > 0)).values,
       'Crescita forte (ricavi 12m >=20%)': (M.revg_ttm >= 0.20).values,
       'In perdita (utile 12m <0)': (M.ni_ttm < 0).values}
rows = []
for nm, m in SUB.items():
    D = M[m]
    for k in ['rk', 't5', 'b20', 'c50']:
        tc = mc.TGT[k]; base = 0 if k == 'rk' else 0.5; S = {}
        for mdl in ['gbm', 'gbm1', 'lin', 'apr']:
            c = f'{mdl}_{k}'
            S[mdl] = mc.ic_by_date(D[c].values, D[tc].values, D.date.values) if k == 'rk' else mc.auc_by_date(D[c].values, D[tc].values, D.date.values)
        d = (S['gbm'] - S['lin']).dropna(); d1 = (S['gbm'] - S['gbm1']).dropna()
        per = [d[[mc.perlab(x) == p for x in d.index]].mean() for p in mc.PERS]
        rows.append(dict(sottouniverso=nm, righe_per_data=len(D) / D.date.nunique(), target=k, gbm=S['gbm'].mean(), gbm1=S['gbm1'].mean(), lin=S['lin'].mean(),
                         apr=S['apr'].mean(), t_gbm=fv3.nw_t(S['gbm'] - base, 4), t_lin=fv3.nw_t(S['lin'] - base, 4),
                         gbm_meno_lin=d.mean(), t_diff=fv3.nw_t(d, 4), gbm_meno_gbm1=d1.mean(), t_diff1=fv3.nw_t(d1, 4),
                         diff_2016=per[0], diff_2017_21=per[1], diff_2022_26=per[2]))
T = pd.DataFrame(rows); T.to_csv(f'{mc.OUT}/profili.csv', index=False)
pd.set_option('display.width', 250); print(T.round(3).to_string())
