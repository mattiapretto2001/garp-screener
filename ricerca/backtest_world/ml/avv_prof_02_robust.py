# avv_prof_02 (verifica avversariale): robustezza del punteggio M0 (fuori campione 2015-2026) a tagli di periodo, regione, taglia,
# code dei rendimenti, costi e societa' dominanti. Misure: Q5-U e Q1-U (CAGR, lordo e netto), differenza aritmetica Q5-U con t NW(2),
# IC (rango dentro profilo vs rango a 12 mesi nella regione) con t NW(4).
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
O2 = f'{HERE}/avv_prof_out'
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
cg = lambda r: (1 + r).prod() ** (4 / len(r)) - 1 if len(r) else np.nan


def measure(X, s, date_keep=None, ret='r_eur', cost=0.0, ic_dates=None):
    """quintili rifatti dentro X (sotto-universo), U = media a pesi uguali di X; date_keep filtra i trimestri dopo la formazione"""
    q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
    U = X.groupby('date')[ret].mean()
    r5 = X[q == 5].groupby('date')[ret].mean().reindex(U.index); r1 = X[q == 1].groupby('date')[ret].mean().reindex(U.index)
    if cost:
        mem = X.index[q == 5]; Dm = X.loc[mem].groupby('date').t.apply(set); prev = set(); tc = {}
        for d in U.index:
            k = Dm.get(d, set()); sold = len(prev - k) / len(prev) if prev else 0; bought = len(k - prev) / len(k) if k else 0
            tc[d] = cost * (sold + bought); prev = k
        tc = pd.Series(tc); r5 = r5 - tc
    if date_keep is not None:
        U, r5, r1 = U[date_keep(U.index)], r5[date_keep(U.index)], r1[date_keep(U.index)]
    d = (r5 - U).dropna()
    Zr = s.groupby(X.date).rank(pct=True).to_frame('s'); ic = ic_matrix(Zr, X.rk12_reg, X.date, min_n=20)['s']
    if ic_dates is not None: ic = ic[ic_dates(ic.index)]
    return dict(n_med=int(X.groupby('date').size().median()), Q5_U=cg(r5) - cg(U), Q1_U=cg(r1) - cg(U), arit=d.mean() * 4, t_arit=nwt(d, 2),
                IC=ic.mean(), t_IC=nwt(ic), n_q=len(d))


rows = []
for k in PNAME:
    s0 = SC[k]['M0'].astype(float); X0 = B.loc[s0.index]
    # rendimento con la coda alta tagliata al 99 percentile per data (calcolato su tutto l'universo B)
    p99 = B.groupby('date').r_eur.quantile(0.99)
    X0 = X0.assign(r_cl=np.minimum(X0.r_eur, X0.date.map(p99)))
    V = {
        'base': (X0, s0, {}),
        'netto 0,5% (Q5)': (X0, s0, dict(cost=COST)),
        'senza 2025-26': (X0, s0, dict(date_keep=lambda i: i < '2024-12-31', ic_dates=lambda i: i <= '2023-12-31')),
        'senza 2020': (X0, s0, dict(date_keep=lambda i: i.year != 2020, ic_dates=lambda i: ~((i >= '2019-03-31') & (i <= '2020-12-31')))),
        'solo 2015-19': (X0, s0, dict(date_keep=lambda i: i < '2019-12-31', ic_dates=lambda i: i <= '2018-12-31')),
        'coda alta 1% tagliata': (X0, s0, dict(ret='r_cl')),
    }
    for nm, m in [('senza Asia', X0.reg_rob != 'Asia'), ('solo USA', X0.reg_rob.isin(['USA grandi', 'USA piccole/medie'])),
                  ('fuori USA', ~X0.reg_rob.isin(['USA grandi', 'USA piccole/medie'])), ('>=1 Mld$', X0.mcap_usd >= 1e9), ('>=2 Mld$', X0.mcap_usd >= 2e9),
                  ('>=2 Mld$ netto', X0.mcap_usd >= 2e9)]:
        V[nm] = (X0[m], s0[m.values], dict(cost=COST) if 'netto' in nm else {})
    for nm, (X, s, kw) in V.items():
        rows.append(dict(profilo=k, variante=nm, **measure(X, s, **kw)))
    # societa' dominanti: tolgo dal profilo (Q5 e universo) le 10 societa' che contribuiscono di piu' all'eccesso del Q5
    q = np.ceil(s0.groupby(X0.date).rank(pct=True) * 5).clip(1, 5); U = X0.groupby('date').r_eur.mean()
    X5 = X0[q == 5]; n5 = X5.groupby('date').size()
    contrib = ((X5.r_eur - X5.date.map(U)) / X5.date.map(n5)).groupby(X5.t).sum().sort_values(ascending=False)
    for ntop in (10, 25):
        top = set(contrib.head(ntop).index); m = ~X0.t.isin(top)
        rows.append(dict(profilo=k, variante=f'senza le {ntop} societa piu redditizie del Q5', **measure(X0[m], s0[m.values])))
    print(k, 'primi contributori Q5:', ', '.join(f'{t} {v * 100:.1f}' for t, v in contrib.head(8).items()), flush=True)
R = pd.DataFrame(rows); R.to_csv(f'{O2}/02_robustezza.csv', index=False); pd.set_option('display.width', 250)
for c in ['Q5_U', 'Q1_U', 'arit', 'IC']: R[c] = R[c].astype(float)
print(R.pivot_table(index='variante', columns='profilo', values='Q5_U', sort=False).mul(100).round(1).to_string())
print(R.pivot_table(index='variante', columns='profilo', values='t_arit', sort=False).round(2).to_string())
print(R.pivot_table(index='variante', columns='profilo', values='Q1_U', sort=False).mul(100).round(1).to_string())
print(R.pivot_table(index='variante', columns='profilo', values='IC', sort=False).round(3).to_string())
print(R.pivot_table(index='variante', columns='profilo', values='t_IC', sort=False).round(2).to_string())
