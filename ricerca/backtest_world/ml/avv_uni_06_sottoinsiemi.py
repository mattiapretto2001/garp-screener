# avv_uni_06 (verifica avversariale): sotto-universi del report (non profittevoli, alta crescita): Holm e periodo pulito >=2018
import numpy as np, pandas as pd
from univariata_common import *
S = pd.read_csv(f'{OUT}/sottoinsiemi.csv')
print('sopravvissute a Holm su rk:'); print(S[(S.tgt == 'rk') & (S.p_holm < 0.05)][['sub', 'var', 'mean', 't']].round(3).to_string(index=False))
F = load_dev()
dates = np.sort(F.date.unique()); DI = {d: i for i, d in enumerate(dates)}
SUB = {'nonprof': F.ni_ttm <= 0, 'altacresc': F.revg_ttm >= 0.20}
V = {'nonprof': ['runway_y', 'npm', 'fcfy', 'fcf_m', 'opm_std5', 'revg_std5', 'capex_int', 'burner', 'dsh3', 'ev_sales', 'hi52'],
     'altacresc': ['hi52', 'n_beat4', 'n_est4', 'mom6', 'runway_y', 'surp_mean4', 'opm_std5', 'capex_int', 'dsh3', 'd_opm', 'vol1y']}
for sn, mask in SUB.items():
    for v in V[sn]:
        out = []
        for nm, m in [('tutto', mask), ('>=2018', mask & (F.date >= '2018-03-31')), ('USA>=2018', mask & (F.date >= '2018-03-31') & (F.reg == 'USA'))]:
            X = F[m]; R = pct_rank(X, [v], ['date', 'reg'])[v]
            cnt = X.groupby(['date', 'reg'], observed=True)[v].transform('count'); R = R.where(cnt >= 10)
            s = pd.Series(group_stat(R.values.astype(float), X.rk12_reg.values.astype(float), X.date.map(DI).values, 'ic', G=len(dates))).dropna()
            out.append(f'{nm} {100*s.mean():+5.1f} (t {fv3.nw_t(s,4):+.1f}, n {len(s)})')
        print(f'{sn:9s} {v:10s}', ' | '.join(out))
