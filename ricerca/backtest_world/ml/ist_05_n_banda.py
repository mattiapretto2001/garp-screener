# ist_05: (1) rischio per numero di titoli N (scarto dal VWCE, perdita massima, peggiore finestra di 3 anni);
# (2) regola di oggi con banda di tolleranza piu' larga (si riequilibra solo se il peso devia oltre il 10/25/50%);
# a lambda 1 e 1/3. Netto di tasse.
import sys, os, pickle, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
RET0 = ic.RET
def set_lambda(lam):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
def mdd(r):
    w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()
rows = []
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for p in ('2018-26', '2012-17'):
        ds = pdates(p); vw = sim_vwce(ds)['twr']
        for lk, N in itertools.product(['core', 'core_noTWKO', 'cr2', 'mix', 'top30'], (8, 10, 12, 15, 20)):
            for lab, rule, kw in [('a f1 banda10', 'a', dict(band=0.10)), ('a f1 banda25', 'a', dict(band=0.25)), ('a f1 banda50', 'a', dict(band=0.50)),
                                  ('a2', 'a2', {}), ('b K15 M30 g1', 'b', dict(K=15, M=30, grace=1))]:
                r = sim(CFG[lk](N), rule, ds, **kw); s = r['twr']; yrs = (NXT[ds[-1]] - ds[0]).days / 365.25
                ex = s - vw
                rows.append(dict(lam=lam, periodo=p, lista=lk, N=N, cfg=lab, irr=r['irr'], te=ex.std() * 2, mdd=mdd(s), mdd_vw=mdd(vw),
                                 worst4=((1 + s).rolling(4).apply(np.prod, raw=True) - (1 + vw).rolling(4).apply(np.prod, raw=True)).min(),
                                 ordini=r['orders'] / yrs, costi=(r['fees'] + r['spread']) / r['vmean'] / yrs, fee_share=r['fees'] / (r['fees'] + r['spread'])))
T = pd.DataFrame(rows); T.to_csv(f'{OUTD}/ist_05_n_banda.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
X = T[(T.lam == 1.0) & (T.periodo == '2018-26')]
print(X.pivot_table(index=['cfg'], columns='N', values=['irr', 'ordini', 'costi']).round(3).to_string())
print(X[X.cfg == 'a f1 banda10'].pivot_table(index='lista', columns='N', values=['te', 'mdd', 'worst4']).round(3).to_string())
X = T[(T.lam < 1) & (T.periodo == '2018-26')]
print('lambda 1/3'); print(X.pivot_table(index=['cfg'], columns='N', values=['irr']).round(3).to_string())
print(X[X.cfg == 'a f1 banda10'].pivot_table(index='lista', columns='N', values=['te', 'mdd', 'worst4']).round(3).to_string())
print('fee share', T.fee_share.describe())
