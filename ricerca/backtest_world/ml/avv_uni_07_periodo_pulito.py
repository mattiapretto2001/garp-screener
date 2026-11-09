# avv_uni_07 (verifica avversariale): conteggi |t| e Holm sul solo periodo con societa' uscite presenti (date >= 31/03/2018)
import numpy as np, pandas as pd
from scipy import stats
from univariata_common import *
SER = pd.read_pickle(f'{OUT}/ic_series.pkl')
rows = []
for v in fv3.PREDICTORS:
    for tk in TGT_MAIN:
        s = SER[('pool', v, tk)].dropna(); s = s[s.index >= pd.Timestamp('2018-03-31')]
        e = s - s.mean(); T = len(s); var = e @ e / T
        for l in range(1, 4): var += 2 * (e.values[l:] @ e.values[:-l]) / T
        rows.append(dict(var=v, tgt=tk, mean=s.mean(), t4=fv3.nw_t(s, 4), thh=s.mean() / np.sqrt(var / T) if var > 0 else np.nan, n=T))
R = pd.DataFrame(rows)
for c in ['t4', 'thh']:
    R['p_' + c] = 2 * stats.t.sf(R[c].abs(), R.n - 1); R['h_' + c] = holm(R['p_' + c].fillna(1).values)
print('date', R.n.max())
print(R.groupby('tgt').apply(lambda d: pd.Series({'|t4|>=2,5': (d.t4.abs() >= 2.5).sum(), 'Holm t4': (d.h_t4 < .05).sum(),
                                                  '|tHH|>=2,5': (d.thh.abs() >= 2.5).sum(), 'Holm HH': (d.h_thh < .05).sum()})))
print('rk, Holm t4:', R[(R.tgt == 'rk') & (R.h_t4 < .05)]['var'].tolist())
print('rk, |t4|>=2,5:', R[(R.tgt == 'rk') & (R.t4.abs() >= 2.5)].sort_values('t4')[['var', 'mean', 't4', 'thh']].round(3).to_string(index=False))
F = fv3.load(cols=['date', 'reg', 'crash50', 'bankrupt12', 'delist12'])
F = F[F.crash50.notna()]
print(F.groupby(F.date.dt.year)[['crash50', 'bankrupt12', 'delist12']].mean().round(4).T.to_string())
R.to_csv(f'{OUT}/avv_periodo_pulito.csv', index=False)
