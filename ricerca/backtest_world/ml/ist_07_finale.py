# ist_07: regola consigliata (trimestrale, N = 12, K = M = 12, banda di riequilibrio +-25%; Crescita K 15 M 30) contro
# "oggi alla lettera" (tutta la lista, pesi uguali ogni trimestre) e contro VWCE, per lista e periodo, lambda 1 e 1/3,
# lordo e netto di tasse; t di Newey-West sulla differenza trimestrale; anni in cui batte VWCE.
import sys, os, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
RET0 = ic.RET
def set_lambda(lam):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
def mdd(r):
    w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()
RUNS = {   # etichetta -> (regola, parametri, N)
    'lista intera (oggi)': ('a', dict(band=0.10), 999),
    'oggi con N=12': ('a', dict(band=0.10), 12),
    'consigliata N=12 banda 25%': ('a', dict(band=0.25), 12),
    'consigliata N=15 banda 25%': ('a', dict(band=0.25), 15),
    'isteresi K15 M30 N=12': ('b', dict(K=15, M=30, grace=1), 12),
    'isteresi K15 M30 N=15': ('b', dict(K=15, M=30, grace=1), 15),
}
rows = []
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for p in PER:
        ds = pdates(p); yrs = (NXT[ds[-1]] - ds[0]).days / 365.25
        for tax in (True, False):
            v = sim_vwce(ds, tax=tax)
            rows.append(dict(lam=lam, periodo=p, lista='VWCE', cfg='VWCE', tasse=tax, irr=v['irr'], W=v['W'], versato=v['contrib'], mdd=mdd(v['twr'])))
            for lk, (lab, (rule, kw, N)) in itertools.product(['core', 'core_noTWKO', 'cr2', 'mix', 'top30'], RUNS.items()):
                r = sim(CFG[lk](N), rule, ds, tax=tax, **kw)
                ex = r['twr'] - v['twr']
                yy = pd.Series(ex.values, index=[d.year + (d.month == 12) for d in ex.index])
                rows.append(dict(lam=lam, periodo=p, lista=lk, cfg=lab, tasse=tax, irr=r['irr'], W=r['W'], versato=r['contrib'], mdd=mdd(r['twr']),
                                 d_vwce=r['irr'] - v['irr'], t_vwce=nwt(ex), anni_meglio=np.mean([(1 + g).prod() > 1 for _, g in ex.groupby(yy.index)]),
                                 ordini=r['orders'] / yrs, nhold=r['nhold'], costi=(r['fees'] + r['spread']) / r['vmean'] / yrs,
                                 costi_eur=r['fees'] + r['spread'], fees=r['fees'], tasse_eur=r['taxpaid']))
T = pd.DataFrame(rows); T.to_csv(f'{OUTD}/ist_07_finale.csv', index=False)
pd.set_option('display.width', 260); pd.set_option('display.max_rows', 500)
for lam in (1.0, 1 / 3):
    X = T[(T.lam == lam) & T.tasse]
    print('lambda', round(lam, 2), 'netto IRR')
    print(X.pivot_table(index=['lista', 'cfg'], columns='periodo', values='irr', sort=False).mul(100).round(1).to_string())
X = T[(T.lam == 1) & T.tasse & (T.periodo == '2018-26')]
print(X[['lista', 'cfg', 'irr', 'd_vwce', 't_vwce', 'anni_meglio', 'ordini', 'nhold', 'costi', 'costi_eur', 'fees', 'tasse_eur', 'W', 'mdd']].round(3).to_string())
