# avv_temi_04: la diluizione (dsh3) dentro i temi: riproduzione e robustezza (senza 2025-26, senza Asia, >=2 Mld$, per regione, per periodo)
from avv_temi_common import *
V = pd.read_pickle(f'{OUT}/V.pkl'); C = pd.read_pickle(f'{OUT}/C.pkl')
C = C[C.fwd12_eur.notna()].copy(); C['tema'] = C.B | C.MOM


def within_ic(X, var, tgt, min_n=30):
    X = X[X[var].notna() & X[tgt].notna()]
    g = X.groupby(['date', 'ind']); n = g[var].transform('count')
    rv = (g[var].rank() - 0.5) / n - 0.5; ry = (g[tgt].rank() - 0.5) / n - 0.5
    Z = pd.DataFrame({'d': X.date, 'v': rv, 'y': ry})[n >= 3]
    s = Z.groupby('d').apply(lambda z: (z.v * z.y).sum() / np.sqrt((z.v ** 2).sum() * (z.y ** 2).sum()) if len(z) > min_n else np.nan)
    return s.dropna()


T = C[C.tema]
rows = []
for lab, X in [('base (riproduzione)', T), ('senza esiti 2025-26', T[T.date <= '2023-12-31']), ('senza date 2025-26', T[T.date < '2025-01-01']),
               ('senza Asia', T[T.reg != 'Asia']), ('solo >=2 Mld$', T[T.mcap_usd >= 2e9]), ('senza us_new', T[~T.us_new.astype(bool)]),
               ('USA grandi', T[T.reg_rob == 'USA grandi']), ('USA piccole/medie', T[T.reg_rob == 'USA piccole/medie']),
               ('Europa', T[T.reg_rob == 'Europa']), ('Asia', T[T.reg_rob == 'Asia']),
               ('2012-16', T[T.date <= '2016-09-30']), ('2017-21', T[(T.date > '2016-09-30') & (T.date <= '2021-09-30')]), ('2022-26', T[T.date > '2021-09-30']),
               ('industrie NON tema', C[~C.tema]), ('tutte le industrie', C)]:
    s = within_ic(X, 'dsh3', 'rk12_reg', min_n=30 if len(X) > 20000 else 10)
    rows.append({'insieme': lab, 'date': len(s), 'IC': round(s.mean(), 4), 't_NW4': round(nw_t(s, 4), 2)})
R = pd.DataFrame(rows); print(R.to_string(index=False)); R.to_csv(f'{OUT}/04_diluizione.csv', index=False)
# effetto in punti: quintili di dsh3 dentro industria (temi), eccesso vs propria industria a 12 mesi
T = T.copy(); T['xs_ind'] = T.fwd12_eur - T.groupby(['date', 'ind']).fwd12_eur.transform('mean')
q = pd.cut(T.groupby(['date', 'ind']).dsh3.rank(pct=True), [0, .2, .4, .6, .8, 1], labels=[1, 2, 3, 4, 5])
G = T.assign(q=q).groupby(['date', 'q'], observed=True).xs_ind.mean().unstack()
print('\nquintili dsh3 (1 = meno diluizione), eccesso vs industria pp:', (100 * G.mean()).round(2).to_dict(), '| Q1-Q5 t NW4 %.2f' % nw_t(G[1] - G[5], 4))
# senza l'1% migliore: il quintile 5 (piu' diluizione) e' fatto di "lotterie"?
T2 = T[T.fwd12_eur < T.groupby('date').fwd12_eur.transform(lambda s: s.quantile(0.99))]
q2 = pd.cut(T2.groupby(['date', 'ind']).dsh3.rank(pct=True), [0, .2, .4, .6, .8, 1], labels=[1, 2, 3, 4, 5])
G2 = T2.assign(q=q2).groupby(['date', 'q'], observed=True).xs_ind.mean().unstack()
print('senza 1% migliore:', (100 * G2.mean()).round(2).to_dict(), '| Q1-Q5 t NW4 %.2f' % nw_t(G2[1] - G2[5], 4))
# Holm sulla famiglia intera delle letture principali (~130): quanto valgono i migliori risultati?
bv = pd.read_csv(f'{HERE}/temi_out/b_varianti.csv'); ai = pd.read_csv(f'{HERE}/temi_out/a_industrie.csv'); bd = pd.read_csv(f'{HERE}/temi_out/b_dentro_temi.csv')
tt = []
for _, r in bv.iterrows():
    for k in ['3m', '12m', '36m', 'top5', 'crollo', 'x3']: tt.append((f'{r.regola} {k}', r['t_' + k]))
tt.append(('Aplus 12m', ai.set_index('regola').loc['Aplus', 't_soc']))
for _, r in bd.iterrows(): tt.append((f'dentro {r["var"]} {r.target}', r.t_temi))
cs = pd.read_csv(f'{HERE}/temi_out/c_screener.csv')
for _, r in cs.iterrows():
    if np.isfinite(r.t): tt.append((f'screener {r.portafoglio}', r.t))
TT = pd.DataFrame(tt, columns=['prova', 't']).dropna(); TT['p'] = [tp(x) for x in TT.t]; TT['p_holm'] = holm(TT.p.values)
TT['p_bonf'] = (TT.p * len(TT)).clip(upper=1)
print('\nfamiglia di', len(TT), 'letture; t-soglia Bonferroni 5%% bilaterale ~ %.2f' % (__import__('scipy.stats', fromlist=['norm']).norm.ppf(1 - 0.025 / len(TT))))
sel = TT[TT.prova.str.contains('CALDE crollo|MOM 3m|MOM top5|BM 3m|dentro dsh3 rk12|BM x3|CALDE 36m|B 3m')]
print(sel.round(4).to_string(index=False))
print('letture con |t|>2: %d su %d (attese per caso ~%.0f)' % ((TT.t.abs() > 2).sum(), len(TT), 0.0455 * len(TT)))
print('quante di queste sono le prove dentro i temi su eccezionali/disastri (effetto "lotteria" ovvio):', ((TT.t.abs() > 2) & TT.prova.str.contains('top5_reg|bot20_reg')).sum())
