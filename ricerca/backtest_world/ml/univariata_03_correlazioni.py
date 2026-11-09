# univariata_03: correlazioni di rango fra le 81 variabili (media delle correlazioni data per data, ranghi dentro data x regione)
# e gruppi di variabili ridondanti (cluster gerarchico, distanza 1-|rho|, legame medio, taglio a |rho| medio 0,6).
import numpy as np, pandas as pd, time
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
from univariata_common import *
t0 = time.time()
F = load_dev(); P = fv3.PREDICTORS
R = pct_rank(F, P, ['date', 'reg'])
mats = []
for d, idx in F.groupby('date').groups.items():
    mats.append(R.loc[idx, P].astype(float).corr(min_periods=200).values)
C = pd.DataFrame(np.nanmean(np.stack(mats), axis=0), index=P, columns=P)
C.to_csv(f'{OUT}/corr_media.csv')
A = C.abs().fillna(0).values.copy(); np.fill_diagonal(A, 1)
D = 1 - A; D = (D + D.T) / 2; np.fill_diagonal(D, 0)
Z = linkage(squareform(D, checks=False), 'average')
lab = fcluster(Z, t=0.4, criterion='distance')
S = pd.read_csv(f'{OUT}/ic_summary.csv')
W = S.pivot(index='var', columns='tgt', values='t')
fam = S.groupby('var').fam.first()
rows = []
for k in np.unique(lab):
    mem = [P[i] for i in np.where(lab == k)[0]]
    if len(mem) < 2: continue
    sub = C.loc[mem, mem].values; iu = np.triu_indices(len(mem), 1)
    best = max(mem, key=lambda v: abs(W.loc[v, 'rk']) + abs(W.loc[v, 'bot20']))
    rows.append(dict(cluster=k, n=len(mem), rho_medio=np.nanmean(np.abs(sub[iu])), rho_min=np.nanmin(np.abs(sub[iu])),
                     membri=', '.join(f'{v}({W.loc[v, "rk"]:+.1f}/{W.loc[v, "bot20"]:+.1f})' for v in mem), migliore=best))
K = pd.DataFrame(rows).sort_values('n', ascending=False)
K.to_csv(f'{OUT}/cluster.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 200)
print('cluster con >=2 membri:', len(K), ' variabili isolate:', len(P) - K.n.sum())
print(K.to_string(index=False))
pairs = [(P[i], P[j], C.iloc[i, j]) for i in range(len(P)) for j in range(i + 1, len(P)) if abs(C.iloc[i, j]) >= 0.7]
print('\ncoppie |rho|>=0.7:', len(pairs))
for a, b, r in sorted(pairs, key=lambda x: -abs(x[2])): print(f'{a:14s} {b:14s} {r:+.2f}')
# correlazione con le variabili 'di rischio' (volatilita', capitalizzazione): quanto ogni variabile e' un travestimento del rischio
print('\ncorrelazione con vol1y e logmcap:')
print(C[['vol1y', 'logmcap']].round(2).sort_values('vol1y').T.to_string())
print('fine', round(time.time() - t0))
