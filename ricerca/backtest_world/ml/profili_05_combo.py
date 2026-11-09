# profili_05: (a) uso del punteggio come "guardia" (tenere la meta' alta del profilo); (b) societa' alte su piu' profili.
# Punteggi fuori campione 2015-2026. Versione principale: M0 per tutti (nessuna scelta a posteriori); secondaria: il metodo migliore per profilo.
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
SCELTO = {'QUAL': 'M1', 'GARP': 'M0', 'CRESC': 'M0', 'PREPROF': 'M0', 'TEMI': 'M1'}
pd.set_option('display.width', 250)


def maxdd(r): w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()


# (a) guardia: meta' alta vs meta' bassa del profilo
G = []
for k in PNAME:
    for m in sorted({'M0', SCELTO[k]}):
        s = SC[k][m].astype(float); X = B.loc[s.index]; v = X.fwd12_eur.notna()
        q = s.groupby(X.date).rank(pct=True); hi = q > 0.5
        G.append(dict(profilo=k, metodo=m, ecc_tenuti=X.top5_reg[v & hi].sum() / X.top5_reg[v].sum(),
                      dis_tenuti=X.bot20_reg[v & hi].sum() / X.bot20_reg[v].sum(), crolli_tenuti=X.crash50[v & hi].sum() / X.crash50[v].sum(),
                      rk_alta=X.rk12_reg[v & hi].mean(), rk_bassa=X.rk12_reg[v & ~hi].mean(),
                      r_alta=cagr_q(X[hi].groupby('date').r_eur.mean()), r_bassa=cagr_q(X[~hi].groupby('date').r_eur.mean()),
                      dd_alta=maxdd(X[hi].groupby('date').r_eur.mean()), dd_bassa=maxdd(X[~hi].groupby('date').r_eur.mean())))
G = pd.DataFrame(G); print(G.round(3).to_string(index=False)); G.to_csv(f'{OUT}/guardia.csv', index=False)

# (b) combinazione
for tag, pick in [('M0', {k: 'M0' for k in PNAME}), ('scelto', SCELTO)]:
    pct = pd.concat({k: SC[k][pick[k]].astype(float).groupby(B.loc[SC[k].index, 'date']).rank(pct=True) for k in PNAME}, axis=1)
    pct.index = pct.index.get_level_values(-1) if isinstance(pct.index, pd.MultiIndex) else pct.index
    X = B.loc[pct.index].copy()
    X['n_prof'] = pct.notna().sum(axis=1); X['n_alti'] = (pct >= 0.8).sum(axis=1); X['pct_media'] = pct.mean(axis=1)
    X['xs'] = (X.fwd12_eur - X.fwd12_eur.groupby(X.date).transform('mean')).clip(-1, 3)
    X['cl'] = np.where(X.n_alti >= 2, '2+ alti', np.where(X.n_alti == 1, '1 alto', '0 alti'))
    v = X.fwd12_eur.notna()
    T = X[v].groupby('cl').agg(righe_per_data=('t', lambda s: len(s) / X.date.nunique()), xs=('xs', 'mean'), rango=('rk12_reg', 'mean'),
                               ecc=('top5_reg', 'mean'), dis=('bot20_reg', 'mean'), crollo=('crash50', 'mean'))
    U = X.groupby('date').r_eur.mean(); rows = []
    for c in ['0 alti', '1 alto', '2+ alti']:
        r = X[X.cl == c].groupby('date').r_eur.mean().reindex(U.index).fillna(0)
        rows.append(dict(cl=c, cagr=cagr_q(r), diff=cagr_q(r) - cagr_q(U), t=(r - U).mean() / (r - U).std() * np.sqrt(len(r)), maxdd=maxdd(r),
                         **{p: cagr_q(r[(r.index.year >= a) & (r.index.year <= b)]) - cagr_q(U[(U.index.year >= a) & (U.index.year <= b)]) for p, (a, b) in list(OOSP.items())[:3]}))
    T = T.join(pd.DataFrame(rows).set_index('cl'))
    # top 20 per (n_alti, pct media) contro top 20 per pct media senza contare i profili
    for nm, sc in [('top20 combinato', X.n_alti + X.pct_media), ('top20 solo media', X.pct_media)]:
        r, picks = run_top(X, sc, 20); P = X.loc[np.concatenate(list(picks.values()))]
        T.loc[nm, ['cagr', 'diff', 't', 'maxdd', 'ecc', 'dis', 'crollo']] = [cagr_q(r), cagr_q(r) - cagr_q(U), (r - U).mean() / (r - U).std() * np.sqrt(len(r)),
                                                                           maxdd(r), P.top5_reg.mean(), P.bot20_reg.mean(), P.crash50.mean()]
        for p, (a, b) in list(OOSP.items())[:3]:
            T.loc[nm, p] = cagr_q(r[(r.index.year >= a) & (r.index.year <= b)]) - cagr_q(U[(U.index.year >= a) & (U.index.year <= b)])
    T.loc['pool', ['cagr', 'ecc', 'dis', 'crollo']] = [cagr_q(U), X[v].top5_reg.mean(), X[v].bot20_reg.mean(), X[v].crash50.mean()]
    print(f'\n== combinazione ({tag})'); print(T.round(3).to_string())
    T.to_csv(f'{OUT}/combinazione_{tag}.csv')
    # quali coppie di profili tra i 2+ alti
    al = (pct >= 0.8); pairs = al[X.n_alti >= 2].apply(lambda r: '+'.join([c for c in pct.columns if r[c]]), axis=1).value_counts(normalize=True).head(6)
    print(pairs.round(3).to_dict())
