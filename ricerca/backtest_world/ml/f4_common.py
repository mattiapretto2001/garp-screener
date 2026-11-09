# f4_common: valutazione comune dei segnali F4 (regole fissate prima: f4_out/REGOLE_PRIMA.txt)
import os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f'{HERE}/f4_out'
TG = {'x3': 'x3 in 3 anni', 'top5_reg': 'top 5% a 12m', 'crash50': 'disastro (-50% a 12m)'}
CLEAN0 = pd.Timestamp('2018-03-31')
RNG = np.random.default_rng(7)


def load():
    F = pd.read_pickle(f'{HERE}/features_v3.pkl')
    F = F[['t', 'date', 'name', 'ex', 'reg', 'reg_rob', 'logmcap', 'n_est4', 'age_y', 'hist_y', 'sh', 'GARP', 'core', 'excl_sector',
           'x3', 'top5_reg', 'crash50', 'fwd12_loc']].copy()
    F['size3'] = F.groupby(['date', 'reg']).logmcap.transform(lambda s: pd.qcut(s.rank(method='first'), 3, labels=False))
    return F


def evaluate(F, sig, base, label, n_draw=1000):
    """sig, base: maschere booleane. Confronto del gruppo (sig & base) con il caso: stessa data, regione e terzile di taglia,
    pescando dentro base. Restituisce una riga per target e periodo."""
    out = []
    for tg in TG:
        for per, lo in [('2012-26', pd.Timestamp('2000-01-01')), ('pulito 2018+', CLEAN0)]:
            B = F[base & F[tg].notna() & (F.date >= lo)]
            if tg == 'x3' and per == 'pulito 2018+': B = B[B.date <= '2021-09-30']
            S = sig.reindex(B.index).fillna(False).astype(bool)
            if S.sum() < 5: out.append(dict(segnale=label, target=tg, periodo=per, righe=int(S.sum()))); continue
            y = B[tg].astype(float)
            cell = ['date', 'reg', 'size3']
            g = B.assign(y=y, s=S).groupby(cell)
            agg = g.agg(n=('y', 'size'), h=('y', 'sum'), k=('s', 'sum'))
            hs = B[S].groupby(cell)[tg].sum().reindex(agg.index).fillna(0)
            agg = agg[agg.k > 0]; hs = hs.reindex(agg.index)
            obs = hs.sum() / agg.k.sum()
            exp_sz = (agg.k * agg.h / agg.n).sum() / agg.k.sum()                      # caso stessa taglia
            gr = B.groupby(['date', 'reg'])[tg].mean()
            exp_u = B[S].set_index(['date', 'reg']).index.map(gr).to_numpy().mean()   # universo stessa regione e data
            # estrazioni casuali (ipergeometrica per cella)
            ng, nb, k = agg.h.to_numpy().astype(int), (agg.n - agg.h).to_numpy().astype(int), agg.k.to_numpy().astype(int)
            draws = RNG.hypergeometric(np.repeat(ng[None], n_draw, 0), np.repeat(nb[None], n_draw, 0), np.repeat(k[None], n_draw, 0)).sum(1) / k.sum()
            pct = (draws < obs).mean() + 0.5 * (draws == obs).mean()
            # t non sovrapposto: date di settembre una all'anno (12m) / ogni 3 anni (x3)
            d = agg.assign(hs=hs, e=agg.k * agg.h / agg.n).groupby(level=0)[['hs', 'e', 'k']].sum()
            d = d[[x.month == 9 for x in d.index]]
            if tg == 'x3': d = d[[x.year in (2012, 2015, 2018, 2021) for x in d.index]]
            diff = (d.hs - d.e) / d.k
            tt = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 2 and diff.std() > 0 else np.nan
            out.append(dict(segnale=label, target=tg, periodo=per, righe=int(S.sum()), societa=B[S].t.nunique(),
                            gruppo=obs, caso_taglia=exp_sz, universo=exp_u, rapporto=obs / exp_sz if exp_sz > 0 else np.nan,
                            pct_caso=pct, t_annuale=tt, n_anni=len(diff)))
    return pd.DataFrame(out)


def fmt(D):
    D = D.copy()
    for c in ['gruppo', 'caso_taglia', 'universo']:
        if c in D: D[c] = (D[c] * 100).round(1)
    for c in ['rapporto', 't_annuale', 'pct_caso']:
        if c in D: D[c] = D[c].round(2)
    return D
