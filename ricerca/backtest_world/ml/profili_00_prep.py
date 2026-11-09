# profili_00: appartenenza ai 5 profili, numerosita', sovrapposizioni, ranghi delle variabili DENTRO ogni profilo e data.
from profili_common import *
F = fv3.load()
P, ind = profiles(F)
keep = ['t', 'date', 'name', 'reg', 'reg_rob', 'per3', 'sector', 'mcap_usd', 'r_eur', 'fwd12_eur', 'xs12_reg', 'rk12_reg', 'top5_reg',
        'bot20_reg', 'crash50', 'size', 'core', 'GARP']
B = F[keep].copy(); B['ind'] = ind
for k, m in P.items(): B[k] = m
B.to_pickle(f'{OUT}/base.pkl')
# numerosita'
rows = []
for k, m in P.items():
    n = m.groupby(F.date).sum()
    X = F[m]
    rows.append(dict(profilo=k, righe=int(m.sum()), societa=X.t.nunique(), n_min=int(n.min()), n_med=int(n.median()), n_max=int(n.max()),
                     **{f'quota_{g}': round((X.reg_rob == g).mean(), 3) for g in GROUPS + ['Altri']},
                     fwd12=round(X.fwd12_eur.mean(), 3), top5=round(X.top5_reg.mean(), 3), bot20=round(X.bot20_reg.mean(), 3),
                     crash50=round(X.crash50.mean(), 3), xs12=round(X.xs12_reg.mean(), 3)))
    print(k, n.groupby(n.index.year).mean().round(0).to_dict())
T = pd.DataFrame(rows); print(T.to_string()); T.to_csv(f'{OUT}/profili_numerosita.csv', index=False)
# sovrapposizioni (quota di righe di A che sono anche in B)
K = list(P); O = pd.DataFrame({a: {b: round((P[a] & P[b]).sum() / P[a].sum(), 2) for b in K} for a in K}).T
print(O); O.to_csv(f'{OUT}/profili_sovrapposizioni.csv')
nprof = pd.concat(P, axis=1).sum(axis=1); print('profili per riga', nprof.value_counts().sort_index().to_dict())
# ranghi dentro profilo (tutte le 81 predittive + logmcap gia' inclusa)
for k, m in P.items():
    X = F[m]
    Z = rank_in(X, fv3.PREDICTORS, X.date)
    Z.to_pickle(f'{OUT}/Z_{k}.pkl')
print('fatto')
