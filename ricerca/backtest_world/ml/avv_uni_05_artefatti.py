# avv_uni_05 (verifica avversariale): (a) peso dell'episodio 2021-22; (b) hist_y e fin_age_d come possibili artefatti
# di dati EODHD piu' poveri per le societa' poi uscite dal listino (informazione futura).
import numpy as np, pandas as pd
from univariata_common import *
F = load_dev(); P = fv3.PREDICTORS
SER = pd.read_pickle(f'{OUT}/ic_series.pkl')
V = ['dsh3', 'n_beat4', 'runway_y', 'roic', 'roe', 'hist_y', 'age_y', 'fcfy', 'opm_std5', 'capex_int', 'fin_age_d', 'burner']
print('t NW4 su rango: tutto / senza date 2021-2022 / senza date 2020-2022 / solo 2018-2019 + 2023-2025')
for v in V:
    s = SER[('pool', v, 'rk')].dropna(); y = pd.to_datetime(s.index).year
    a = s[~np.isin(y, [2021, 2022])]; b = s[~np.isin(y, [2020, 2021, 2022])]; c = s[np.isin(y, [2018, 2019, 2023, 2024, 2025])]
    print(f'{v:10s} {100*s.mean():+5.1f} ({fv3.nw_t(s,4):+.1f}) | {100*a.mean():+5.1f} ({fv3.nw_t(a,4):+.1f}) | {100*b.mean():+5.1f} ({fv3.nw_t(b,4):+.1f}) | {100*c.mean():+5.1f} ({fv3.nw_t(c,4):+.1f})')
# (b) USA: hist_y e fin_age_d fra future uscite e quotate, a parita' di data e di eta' dalla IPO
U = F[F.reg == 'USA'].copy()
U['dl'] = U.delisted.astype(bool)
U['age_b'] = pd.cut(U.age_y, [0, 3, 5, 10, 20, 200])
print('\nUSA: hist_y medio per eta dalla IPO, quotate vs uscite')
print(U.groupby(['age_b', 'dl'], observed=True).hist_y.mean().unstack().round(1))
print('USA: fin_age_d mediano per anno, quotate vs uscite')
print(U.groupby([U.date.dt.year, 'dl']).fin_age_d.median().unstack().round(0).T)
print('quota fin_age_d > 150 giorni: quotate', round((U[~U.dl].fin_age_d > 150).mean(), 3), ' uscite', round((U[U.dl].fin_age_d > 150).mean(), 3))
# uscite: fin_age_d negli ultimi 4 trimestri prima dell'uscita vs prima
L = F.groupby('t').date.transform('max')
U['q_to_last'] = ((L[U.index] - U.date).dt.days / 91).round()
print('USA uscite: fin_age_d medio per trimestri mancanti all\'ultima presenza', U[U.dl].groupby('q_to_last').fin_age_d.mean().head(8).round(0).to_dict())
print('USA quotate: idem', U[~U.dl].groupby('q_to_last').fin_age_d.mean().head(8).round(0).to_dict())
# IC di fin_age_d e hist_y dentro le sole quotate oggi e dentro le sole uscite (USA, date>=2018)
dates = np.sort(F.date.unique()); DI = {d: i for i, d in enumerate(dates)}
for v in ['fin_age_d', 'hist_y']:
    for nm, m in [('tutte', F.date >= '2018-03-31'), ('quotate', (F.date >= '2018-03-31') & ~F.delisted.astype(bool)), ('uscite', (F.date >= '2018-03-31') & F.delisted.astype(bool))]:
        X = F[m]; r = pct_rank(X, [v], ['date', 'reg'])[v].values.astype(float)
        for tk in ['rk', 'bot20']:
            s = pd.Series(group_stat(r, X[TGT[tk]].values.astype(float), X.date.map(DI).values, 'ic' if tk == 'rk' else 'auc', G=len(dates))).dropna()
            print(f'{v} {nm:8s} {tk:5s} {100*s.mean():+5.1f} t {fv3.nw_t(s,4):+.1f}')
