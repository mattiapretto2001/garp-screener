# tune_02: i vincitori mancati. Quale filtro GARP esclude i titoli eccezionali, e quanti perdenti toglie in cambio.
import pandas as pd, numpy as np, itertools, sys
from tune_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300); pd.set_option('display.max_columns', 40)
F = load()
F.to_pickle(f'{BASE}/res/tune_panel.pkl')
D = F[F.f12.notna()]
print('osservazioni con f12', len(D), 'date', D.date.nunique(), 'GARP', D.GARP.sum())
print('GARP medio per data', D.groupby('date').GARP.sum().mean())
OK = [f'ok_{f}' for f in FILTERS]
out = []


def block(X, tag):
    W, MB, L, L5 = X[X.W5], X[X.MB3], X[X.L20], X[X.L50]
    rows = []
    for f in FILTERS:
        fail = ~X[f'ok_{f}']
        others = X[[o for o in OK if o != f'ok_{f}']].all(axis=1)
        Y = X[others]; pss = Y[f'ok_{f}']
        rows.append(dict(gruppo=tag, filtro=f,
                         esclusi_univ=fail.mean(),
                         esclusi_W5=(~W[f'ok_{f}']).mean(), unico_W5=((~W[f'ok_{f}']) & (W.n_fail == 1)).mean(),
                         na_W5=W[f'na_{f}'].mean(),
                         esclusi_MB3=(~MB[f'ok_{f}']).mean() if len(MB) else np.nan,
                         unico_MB3=((~MB[f'ok_{f}']) & (MB.n_fail == 1)).mean() if len(MB) else np.nan,
                         esclusi_L20=(~L[f'ok_{f}']).mean(), esclusi_L50=(~L5[f'ok_{f}']).mean() if len(L5) else np.nan,
                         rapporto_L20_W5=(~L[f'ok_{f}']).mean() / max((~W[f'ok_{f}']).mean(), 1e-9),
                         # marginale: fra chi supera gli altri 7 filtri
                         loo_n_pass=pss.sum(), loo_n_fail=(~pss).sum(),
                         loo_W5_pass=Y[pss].W5.mean(), loo_W5_fail=Y[~pss].W5.mean(),
                         loo_L20_pass=Y[pss].L20.mean(), loo_L20_fail=Y[~pss].L20.mean(),
                         loo_f12_pass=Y[pss].f12.median(), loo_f12_fail=Y[~pss].f12.median(),
                         loo_ex_pass=(Y[pss].f12 - Y[pss].date.map(X.groupby('date').f12.median())).mean(),
                         loo_ex_fail=(Y[~pss].f12 - Y[~pss].date.map(X.groupby('date').f12.median())).mean()))
    return rows


out += block(D, 'tutto')
for p in PERIODS: out += block(D[D.per == p], p)
for r in ['USA', 'Europa', 'Asia', 'Altri']: out += block(D[D.reg == r], r)
T = pd.DataFrame(out)
T.to_csv(f'{BASE}/res/tune_killer.csv', index=False)
print(T[T.gruppo == 'tutto'].round(3).to_string())
print('\n--- rapporto perdenti/vincitori esclusi, per gruppo')
print(T.pivot(index='filtro', columns='gruppo', values='rapporto_L20_W5').round(2).to_string())
print('\n--- marginale (fra chi passa gli altri 7): P(W5) passa / non passa')
T['loo_W5_ratio'] = T.loo_W5_pass / T.loo_W5_fail
T['loo_ex_diff'] = T.loo_ex_pass - T.loo_ex_fail
print(T.pivot(index='filtro', columns='gruppo', values='loo_W5_ratio').round(2).to_string())
print(T.pivot(index='filtro', columns='gruppo', values='loo_ex_diff').round(3).to_string())
print(T.pivot(index='filtro', columns='gruppo', values='loo_n_fail').round(0).to_string())

# quota di eccezionali presi dal GARP, numero di filtri falliti
S = []
for g, X in [('tutto', D)] + [(p, D[D.per == p]) for p in PERIODS] + [(r, D[D.reg == r]) for r in ['USA', 'Europa', 'Asia', 'Altri']]:
    W = X[X.W5]; MB = X[X.MB3]
    S.append(dict(gruppo=g, n_W5=len(W), W5_in_GARP=W.GARP.mean(), MB3_in_GARP=MB.GARP.mean() if len(MB) else np.nan,
                  univ_in_GARP=X.GARP.mean(), prec_GARP_W5=X[X.GARP].W5.mean(), prec_GARP_L20=X[X.GARP].L20.mean(),
                  W5_fail1=(W.n_fail == 1).mean(), W5_fail2=(W.n_fail == 2).mean(), W5_fail3p=(W.n_fail >= 3).mean(),
                  W5_settore=W.excl_sector.mean(), W5_perdita=(W.ni_ttm <= 0).mean()))
S = pd.DataFrame(S); S.to_csv(f'{BASE}/res/tune_killer_sintesi.csv', index=False)
print(S.round(3).to_string())

# coppie di filtri che bocciano i vincitori con 2 filtri falliti
W = D[D.W5 & (D.n_fail == 2)]
pairs = W[OK].apply(lambda r: ' + '.join(f for f, o in zip(FILTERS, r) if not o), axis=1).value_counts(normalize=True).head(12)
print('\ncoppie (W5 con 2 filtri falliti):'); print(pairs.round(3).to_string())
pairs.to_csv(f'{BASE}/res/tune_killer_coppie.csv')
# vincitori a un filtro: chi e' il killer
W1 = D[D.W5 & (D.n_fail == 1)]
k1 = W1[OK].apply(lambda r: [f for f, o in zip(FILTERS, r) if not o][0], axis=1).value_counts(normalize=True)
print('\nkiller unico (W5 con 1 filtro fallito):'); print(k1.round(3).to_string())
# stessa cosa per tutti i titoli con 1 solo filtro fallito: rendimento rispetto al GARP
X1 = D[D.n_fail == 1].copy()
X1['killer'] = X1[OK].apply(lambda r: [f for f, o in zip(FILTERS, r) if not o][0], axis=1)
med = D.groupby('date').f12.median()
X1['ex'] = X1.f12 - X1.date.map(med)
G = D[D.GARP].assign(ex=lambda x: x.f12 - x.date.map(med))
k = X1.groupby('killer').agg(n=('t', 'size'), W5=('W5', 'mean'), L20=('L20', 'mean'), ex=('ex', 'mean'), ex_med=('ex', 'median'))
k.loc['(GARP promossi)'] = [len(G), G.W5.mean(), G.L20.mean(), G.ex.mean(), G.ex.median()]
k.loc['(universo)'] = [len(D), D.W5.mean(), D.L20.mean(), 0, (D.f12 - D.date.map(med)).median()]
print('\nquasi-promossi (1 solo filtro fallito):'); print(k.round(3).to_string())
k.to_csv(f'{BASE}/res/tune_quasi_promossi.csv')
kp = X1.groupby(['killer', 'per']).agg(n=('t', 'size'), W5=('W5', 'mean'), ex=('ex', 'mean')).unstack()
print(kp.round(3).to_string())
kr = X1.groupby(['killer', 'reg']).agg(W5=('W5', 'mean'), ex=('ex', 'mean')).unstack()
print(kr.round(3).to_string())
# esempi: i multi-bagger piu' grandi mancati dal GARP (prima data in cui sono nell'universo con f36>=2)
M = F[F.MB3 & ~F.GARP].sort_values('f36', ascending=False)
M['killer'] = M[OK].apply(lambda r: ', '.join(f for f, o in zip(FILTERS, r) if not o), axis=1)
ex = M.groupby('t').head(1).head(40)[['name', 'reg', 'date', 'f36', 'killer', 'revq', 'peg', 'roe', 'mcap_usd']]
print(ex.to_string())
ex.to_csv(f'{BASE}/res/tune_esempi_mancati.csv', index=False)
