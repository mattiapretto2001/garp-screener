# univariata_06: controllo anti-artefatto. Variabili che misurano la "disponibilita' dei dati" (stime degli analisti, anni di storia)
# potrebbero essere piu' basse per le societa' poi uscite dal listino solo perche' EODHD ne conserva meno dati.
# Diagnostica (NON usata per scegliere): IC dentro le sole societa' oggi quotate e dentro le sole uscite (delisted = info futura).
import numpy as np, pandas as pd
from univariata_common import *
F = load_dev()
V = ['n_est4', 'n_beat4', 'surp_mean4', 'hist_y', 'age_y', 'dsh3', 'runway_y', 'fcfy', 'roic', 'hi52']
dates = np.sort(F.date.unique()); DI = {d: i for i, d in enumerate(dates)}
rows = []
for name, m in [('tutte', F.rk12_reg.notna()), ('oggi quotate', ~F.delisted.astype(bool)), ('uscite dal listino', F.delisted.astype(bool))]:
    X = F[m]; gd = X.date.map(DI).astype(int).values
    R = pct_rank(X, V, ['date', 'reg'])
    for v in V:
        for tk in ['rk', 'bot20']:
            s = pd.Series(group_stat(R[v].values.astype(float), X[TGT[tk]].values.astype(float), gd, 'ic' if tk == 'rk' else 'auc', G=len(dates))).dropna()
            rows.append(dict(pop=name, var=v, tgt=tk, mean=s.mean(), t=fv3.nw_t(s, 4)))
    print(name, 'righe', len(X), 'n_est4 medio', round(X.n_est4.mean(), 2), 'n_est4 mancante', round(X.n_est4.isna().mean(), 3), 'hist_y medio', round(X.hist_y.mean(), 1))
D = pd.DataFrame(rows)
print(D.pivot_table(index='var', columns=['tgt', 'pop'], values=['mean', 't']).round(3).to_string())
# USA, societa' simili per taglia: n_est4 medio per fascia di capitalizzazione, quotate vs uscite
U = F[F.reg == 'USA'].copy(); U['taglia'] = pd.qcut(U.logmcap, 4, labels=['q1', 'q2', 'q3', 'q4'])
print(U.groupby(['taglia', 'delisted'], observed=True)[['n_est4', 'hist_y', 'age_y']].mean().round(2))
D.to_csv(f'{OUT}/controlli_artefatti.csv', index=False)
