# regressioni_00: prepara la matrice standardizzata per le regressioni e i gruppi (cluster) di variabili correlate.
# - ranghi per data x regione (reg: USA/Europa/Asia/Altri), con il segno della direzione a priori (1 = meglio secondo l'attesa)
# - z = (rango - 0.5) * sqrt(12)  -> media 0, varianza 1; mancanti lasciati NaN (riempiti con 0 = mediana nei modelli)
# - correlazioni medie di rango fra variabili (data per data, 2012-2026) e cluster gerarchico |rho| > 0.5
# NESSUNA informazione sui rendimenti futuri e' usata qui.
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
OUT = fv3.HERE
F = fv3.load()
P = fv3.PREDICTORS
ctx = ['t', 'date', 'reg', 'reg_rob', 'per3', 'sector', 'excl_sector', 'size', 'ext_fields', 'GARP', 'core', 'mcap_usd',
       'ni_ttm', 'fcf_ttm', 'revg_ttm', 'rev_cagr']
tg = ['r_eur', 'fwd12_eur', 'xs12_reg', 'rk12_reg', 'top5', 'top5_reg', 'bot20', 'bot20_reg', 'crash50']
R = fv3.xs_rank(F, P, by=['date', 'reg'], signed=True)
Z = ((R - 0.5) * np.sqrt(12)).astype('float32')
Z.columns = ['z_' + c for c in P]
M = pd.concat([F[ctx + tg].reset_index(drop=True), Z.reset_index(drop=True)], axis=1)
M.to_pickle(f'{OUT}/reg_Z.pkl')
print('salvato reg_Z.pkl', M.shape)

# correlazioni medie (Spearman = Pearson sui ranghi) data per data, coppie disponibili
dates = sorted(M.date.unique())
acc = np.zeros((len(P), len(P))); cnt = np.zeros_like(acc)
for d in dates[::2]:   # una data su due: basta per la struttura
    X = Z[M.date.values == d].astype(float)
    C = X.corr(min_periods=200).values
    ok = ~np.isnan(C); acc[ok] += C[ok]; cnt[ok] += 1
C = pd.DataFrame(acc / np.maximum(cnt, 1), index=P, columns=P)
C.to_csv(f'{OUT}/reg_corr_media.csv')
D = 1 - C.abs().values; np.fill_diagonal(D, 0); D = (D + D.T) / 2
L = linkage(squareform(D, checks=False), 'average')
cl = fcluster(L, t=0.5, criterion='distance')
cov = F[P].notna().mean()
fam = {v: f for f, vs in fv3.FAMILIES.items() for v in vs}
tab = pd.DataFrame({'cluster': cl, 'famiglia': [fam[p] for p in P], 'copertura': cov.values.round(2)}, index=P)
# variabile piu' 'centrale' del cluster (correlazione media assoluta con gli altri membri)
cent = {}
for k, g in tab.groupby('cluster'):
    m = g.index.tolist()
    for v in m: cent[v] = C.loc[v, m].abs().mean() if len(m) > 1 else 1.0
tab['centralita'] = pd.Series(cent).round(2)
tab = tab.sort_values(['cluster', 'centralita'], ascending=[True, False])
tab.to_csv(f'{OUT}/reg_cluster.csv')
pd.set_option('display.width', 200)
for k, g in tab.groupby('cluster'):
    print(k, ', '.join(f'{v}({r.copertura:.2f},{r.centralita:.2f})' for v, r in g.iterrows()))
