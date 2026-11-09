# avv_prof_05 (verifica avversariale): (a) meta' alta contro meta' bassa con t e al netto della rotazione; (b) 'alte su 2+ profili'
# con t NW e senza 2025-26; (c) sotto-profili PREPROF veri e TEMI emergenti/esclusi: Q5-U per periodo; (d) composizione del Q5 TEMI.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
cg = lambda r: (1 + r).prod() ** (4 / len(r)) - 1
print('(a) meta alta - meta bassa')
for k in PNAME:
    s = SC[k]['M0'].astype(float); X = B.loc[s.index]; hi = s.groupby(X.date).rank(pct=True) > 0.5
    ra = X[hi].groupby('date').r_eur.mean(); rb = X[~hi].groupby('date').r_eur.mean(); d = ra - rb
    Sa = X[hi].groupby('date').t.apply(set); to = np.mean([1 - len(Sa.iloc[i] & Sa.iloc[i - 1]) / len(Sa.iloc[i]) for i in range(1, len(Sa))])
    print(f'  {k}: CAGR alta {cg(ra):.3f} bassa {cg(rb):.3f}; differenza aritmetica {d.mean() * 4:.3f}/anno t NW2 {nwt(d, 2):.2f};'
          f' rotazione meta alta {to:.0%}/trim; senza 2025-26 aritm. {d[d.index < "2024-12-31"].mean() * 4:.3f} t {nwt(d[d.index < "2024-12-31"], 2):.2f}')
print('(b) alte su 2+ profili (M0)')
pct = pd.concat({k: SC[k]['M0'].astype(float).groupby(B.loc[SC[k].index, 'date']).rank(pct=True) for k in PNAME}, axis=1)
X = B.loc[pct.index].copy(); X['n_alti'] = (pct >= 0.8).sum(axis=1).values
U = X.groupby('date').r_eur.mean()
for c, m in [('0', X.n_alti == 0), ('1', X.n_alti == 1), ('2+', X.n_alti >= 2)]:
    r = X[m].groupby('date').r_eur.mean().reindex(U.index); d = r - U
    print(f'  {c}: CAGR-U {cg(r) - cg(U):.3f}; aritm {d.mean() * 4:.3f} t NW2 {nwt(d, 2):.2f} t semplice {d.mean() / d.std() * np.sqrt(len(d)):.2f};'
          f' senza 2025-26 {cg(r[r.index < "2024-12-31"]) - cg(U[U.index < "2024-12-31"]):.3f}')
print('(c) sotto-profili')
F = fv3.load(cols=['n_loss_5y', 'sector'])
for k, nm, msk in [('PREPROF', 'veri', F.n_loss_5y >= 3), ('PREPROF', 'temporanei', F.n_loss_5y <= 1),
                   ('TEMI', 'esclusi', F.sector.astype(str).isin(COMMOD_SECT)), ('TEMI', 'emergenti', ~F.sector.astype(str).isin(COMMOD_SECT))]:
    s = SC[k]['M0'].astype(float); s = s[msk.reindex(s.index).fillna(False).values]; X = B.loc[s.index]
    q = s.groupby(X.date).rank(pct=True); U = X.groupby('date').r_eur.mean()
    r5 = X[q > 0.8].groupby('date').r_eur.mean().reindex(U.index); d = r5 - U
    ic = ic_matrix(q.to_frame('s'), X.rk12_reg, X.date, min_n=20)['s']
    per = {p: round(cg(r5[(U.index.year >= a) & (U.index.year <= b)]) - cg(U[(U.index.year >= a) & (U.index.year <= b)]), 3) for p, (a, b) in list(OOSP.items())[:3]}
    icp = {p: round(ic[(ic.index.year >= a) & (ic.index.year <= b)].mean(), 3) for p, (a, b) in list(OOSP.items())[:3]}
    print(f'  {k} {nm}: n/data {X.groupby("date").size().median():.0f}; IC {ic.mean():.3f} t {nwt(ic):.2f} per periodo {icp}; Q5-U {cg(r5) - cg(U):.3f} aritm t {nwt(d, 2):.2f} per periodo {per}')
print('(d) TEMI: quota di settori esclusi nel Q5 rispetto al profilo')
s = SC['TEMI']['M0'].astype(float); X = B.loc[s.index]; q = s.groupby(X.date).rank(pct=True)
ex = X.sector.astype(str).isin(COMMOD_SECT)
print(f'  profilo {ex.mean():.2f}, Q5 {ex[q > 0.8].mean():.2f}, Q1 {ex[q <= 0.2].mean():.2f}')
