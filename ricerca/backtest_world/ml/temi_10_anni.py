# temi_10: anno per anno (data di formazione) e contributo delle singole industrie, regole B, MOM, BM, CALDE (12 mesi, eccesso vs regione)
from temi_common import *
V = pd.read_pickle(f'{OUT}/ind_flags2.pkl')
CI = pd.read_pickle(f'{OUT}/comp_ind.pkl')
Fc = fv3.load(cols=['t', 'date', 'xs12_reg', 'r_eur', 'reg'])
C = CI.merge(Fc, on=['t', 'date']).merge(V[['ind', 'date', 'B', 'MOM', 'BM', 'CALDE']], on=['ind', 'date'], how='inner')
C['xs3'] = C.r_eur - C.groupby(['date', 'reg']).r_eur.transform('mean'); C.loc[C.date == C.date.max(), 'xs3'] = np.nan
Y = C[C.xs12_reg.notna()]
rows = {}
for r in ['B', 'MOM', 'BM', 'CALDE']:
    sp = Y[Y[r]].groupby('date').xs12_reg.mean() - Y.groupby('date').xs12_reg.mean()
    s3 = C[C[r]].groupby('date').xs3.mean() - C.groupby('date').xs3.mean()
    rows[r + ' 12m'] = sp.groupby(sp.index.year).mean() * 100
    rows[r + ' 3m'] = s3.groupby(s3.index.year).mean() * 100
A = pd.DataFrame(rows).round(1); print(A.to_string()); A.to_csv(f'{OUT}/e_anni.csv')
print('anni positivi:', {c: f'{(A[c].dropna() > 0).sum()}/{A[c].notna().sum()}' for c in A})
# contributo per industria nella regola B, 2022-26 e 2012-21
V2 = V[V.y_xs.notna()].copy(); V2['rel'] = V2.y_xs - V2.groupby('date').y_xs.transform('mean')
for r in ['B', 'BM']:
    for a, b in (('2011-12-31', '2021-09-30'), ('2021-12-31', '2026-09-30')):
        g = V2[V2[r] & (V2.date >= a) & (V2.date <= b)].groupby('ind').rel.agg(['size', 'mean', 'sum']).sort_values('sum')
        print(f'\n{r} {a[:4]}-{b[:4]}: peggiori', '; '.join(f'{i} {n}x {100*m:+.0f}' for i, (n, m, s) in g.head(5).iterrows()),
              '| migliori', '; '.join(f'{i} {n}x {100*m:+.0f}' for i, (n, m, s) in g.tail(6).iterrows()))
