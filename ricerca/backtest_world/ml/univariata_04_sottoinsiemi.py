# univariata_04: stesse misure (IC / AUC-0,5 per data, t di Newey-West, segno per periodo) DENTRO due sotto-universi
# utili ai profili: S1 'non ancora profittevoli' (utile netto TTM <=0) e S2 'alta crescita' (ricavi TTM +20% o piu' sull'anno).
# I target restano quelli della regione intera (battere il mercato, non gli altri del gruppo).
import numpy as np, pandas as pd, time
from scipy import stats
from univariata_common import *
t0 = time.time()
F = load_dev(); P = fv3.PREDICTORS
SUB = {'nonprof': F.ni_ttm <= 0, 'altacresc': F.revg_ttm >= 0.20}
rows = []
for sn, mask in SUB.items():
    X = F[mask].copy()
    dates = np.sort(X.date.unique()); DI = {d: i for i, d in enumerate(dates)}; gd = X.date.map(DI).astype(int).values
    per_of = X.groupby('date').per3.first().reindex(dates).astype(str).values
    print(sn, 'righe', len(X), 'per data', round(len(X) / len(dates)), 'top5', round(X.top5_reg.mean(), 3), 'bot20', round(X.bot20_reg.mean(), 3),
          'crash', round(X.crash50.mean(), 3))
    R = pct_rank(X, P, ['date', 'reg'])
    cnt = X.groupby(['date', 'reg'], observed=True)[P].transform('count'); R = R.where(cnt >= 10)
    for v in P:
        x = R[v].values.astype(float)
        for tk, tc in TGT.items():
            s = pd.Series(group_stat(x, X[tc].values.astype(float), gd, 'ic' if tk == 'rk' else 'auc', G=len(dates)), index=dates).dropna()
            if len(s) < 20: continue
            row = dict(sub=sn, var=v, tgt=tk, mean=s.mean(), t=fv3.nw_t(s, 4), n=len(s), cov=X[v].notna().mean())
            for p in PERS: row[f'per_{p}'] = s[per_of[[DI[d] for d in s.index]] == p].mean()
            usa = X.reg == 'USA'
            rows.append(row)
S = pd.DataFrame(rows)
S['p'] = 2 * stats.t.sf(S.t.abs(), S.n - 1)
S['n_per_same'] = sum((np.sign(S[f'per_{p}']) == np.sign(S['mean'])).astype(int) for p in PERS)
S['p_holm'] = np.nan
for sn in SUB:
    m = (S['sub'] == sn) & S.tgt.isin(['rk', 'top5', 'bot20', 'crash']); S.loc[m, 'p_holm'] = holm(S.loc[m, 'p'])
S.to_csv(f'{OUT}/sottoinsiemi.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
for sn in SUB:
    W = S[S['sub'] == sn].pivot(index='var', columns='tgt', values=['mean', 't', 'n_per_same'])
    out = pd.DataFrame({'IC': W['mean']['rk'], 't_rk': W['t']['rk'], 'np_rk': W['n_per_same']['rk'], 'top5': W['mean']['top5'], 't5': W['t']['top5'],
                        'bot20': W['mean']['bot20'], 't20': W['t']['bot20'], 'np20': W['n_per_same']['bot20'], 'crash': W['mean']['crash'],
                        'tcr': W['t']['crash']}).round(3)
    out = out[(out.t_rk.abs() >= 2) | (out.t20.abs() >= 2.5) | (out.t5.abs() >= 2.5) | (out.tcr.abs() >= 2.5)]
    print('\n=====', sn); print(out.sort_values('t_rk').to_string())
    m = (S['sub'] == sn); print('Holm<0.05 per target:', S[m & (S.p_holm < 0.05)].groupby('tgt').size().to_dict())
print('fine', round(time.time() - t0))
