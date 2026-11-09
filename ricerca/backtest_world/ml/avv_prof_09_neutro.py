# avv_prof_09 (verifica avversariale): Q5 neutro per regione (quintili dentro data x gruppo di regioni, rendimento meno media del gruppo)
# e neutro per settore (quintili dentro data x settore), per togliere scommesse implicite su regioni o settori andati bene.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
for k in PNAME:
    s = SC[k]['M0'].astype(float); X = B.loc[s.index].copy(); X['s'] = s; out = []
    for nm, g in [('regione', 'reg_rob'), ('settore', 'sector')]:
        X['g'] = X[g].astype(str); grp = X.groupby(['date', 'g'])
        n = grp.s.transform('count'); X['p'] = grp.s.rank(pct=True); X['xr'] = X.r_eur - grp.r_eur.transform('mean')
        ok = n >= 10
        d5 = X[ok & (X.p > 0.8)].groupby('date').xr.mean(); d1 = X[ok & (X.p <= 0.2)].groupby('date').xr.mean()
        out.append(f'neutro per {nm}: Q5 {d5.mean() * 400:+.1f}/anno (t {nwt(d5, 2):.2f}), Q1 {d1.mean() * 400:+.1f} (t {nwt(d1, 2):.2f})')
    print(k, ' | '.join(out))
