# profili_07: punteggio finale = M0 (pesi uguali, segni a priori) per tutti i profili.
# (1) concentrazione: top 10/20/50 e quintile; sensibilita' >=2 Mld$; (2) formule con le prove per variabile; (3) lista al 30/09/2026.
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
F = fv3.load(); P, _ = profiles(F)
U1 = pd.read_csv(f'{OUT}/uni_ic.csv'); FMr = pd.read_csv(f'{OUT}/fm_profili.csv')
pd.set_option('display.width', 250)


def maxdd(r): w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()


rows = []
for k in PNAME:
    s = SC[k]['M0'].astype(float); X = B.loc[s.index]
    for big in [False, True]:
        Xb = X[X.mcap_usd >= 2e9] if big else X; sb = s.loc[Xb.index]
        U = Xb.groupby('date').r_eur.mean()
        for n in [10, 20, 50]:
            r, picks = run_top(Xb, sb, n); Pk = Xb.loc[np.concatenate(list(picks.values()))]
            d = r - U.reindex(r.index)
            row = dict(profilo=k, taglia='>=2 Mld$' if big else 'tutte', n=n, cagr=cagr_q(r), univ=cagr_q(U), diff=cagr_q(r) - cagr_q(U),
                       t=d.mean() / d.std() * np.sqrt(len(d)), maxdd=maxdd(r), ecc=Pk.top5_reg.mean(), dis=Pk.bot20_reg.mean(), crollo=Pk.crash50.mean())
            for p, (a, b) in list(OOSP.items())[:3]:
                mk = (r.index.year >= a) & (r.index.year <= b); row[p] = cagr_q(r[mk]) - cagr_q(U.reindex(r.index)[mk])
            if n == 20: row['batte_caso'] = rand_pct(Xb, 20, r, (2015, 2026), n_it=300)
            rows.append(row)
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/m0_concentrazione.csv', index=False)
print(T.round(3).to_string(index=False))

# formule: variabile, segno, peso, prove nel campione intero (univariata dentro il profilo e multipla)
FO = []
for k in PNAME:
    for c in CAND[k]:
        u = U1[(U1.profilo == k) & (U1['var'] == c)].set_index('target')
        mrow = FMr[(FMr.profilo == k) & (FMr['var'] == c)].set_index('target')
        FO.append(dict(profilo=k, var=c, segno='+' if fv3.DIRECTION[c] > 0 else '-', peso=round(1 / len(CAND[k]), 3),
                       ic_rango=u.loc['rk12_reg', 'ic'], t_rango=u.loc['rk12_reg', 't'], t_ecc=u.loc['top5_reg', 't'], t_dis=u.loc['bot20_reg', 't'],
                       coer_rango=u.loc['rk12_reg', 'coer'], t_multi_rango=mrow.loc['rk12_reg', 't'], t_multi_dis=mrow.loc['bot20_reg', 't']))
FO = pd.DataFrame(FO); FO.to_csv(f'{OUT}/formule_M0.csv', index=False)
print(FO.round(3).to_string(index=False))

# punteggi all'ultima data (30/09/2026) e societa' alte su 2+ profili
d = F.date.max(); L = []
for k in PNAME:
    X = F[P[k] & (F.date == d)]
    sc = (rank_in(X, CAND[k], X.date) - 0.5).mean(axis=1)
    L.append(pd.DataFrame({'profilo': k, 't': X.t, 'name': X.name, 'reg': X.reg_rob, 'mcap_mld': X.mcap_usd / 1e9, 'pct': sc.rank(pct=True)}))
L = pd.concat(L)
W = L.pivot_table(index=['t', 'name'], columns='profilo', values='pct')
W['n_alti'] = (W[list(PNAME)] >= 0.8).sum(axis=1); W['pct_media'] = W[list(PNAME)].mean(axis=1)
W = W.join(L.groupby('t')[['reg', 'mcap_mld']].first(), on='t')
W.to_csv(f'{OUT}/punteggi_2026-09-30.csv')
for k in PNAME:
    x = L[L.profilo == k].sort_values('pct', ascending=False).head(8)
    print(k, '; '.join(f"{r.name} ({r.t}, {r.mcap_mld:.0f})" for r in x.itertuples()))
x = W[W.n_alti >= 2].sort_values(['n_alti', 'pct_media'], ascending=False).head(25)
print(x.round(2).to_string())
print('2+ alti oggi:', (W.n_alti >= 2).sum(), '| >=2 Mld$:', ((W.n_alti >= 2) & (W.mcap_mld >= 2)).sum())
