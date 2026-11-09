# ist_06 (variante aggiunta DOPO aver visto ist_03-05, quindi ottimista): isteresi solo sulla classifica (compra dalla top N,
# vendi se esce dalla lista o scende oltre il 30 posto, subito) PIU' riequilibrio con banda larga (+-50%), contro la regola di oggi
# con banda 10% e 25%. lambda 1 e 1/3, periodi interi e parziali, netto di tasse.
import sys, os, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
RET0 = ic.RET
def set_lambda(lam):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
rows = []
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for p in PER:
        ds = pdates(p); yrs = (NXT[ds[-1]] - ds[0]).days / 365.25
        for lk, N in itertools.product(['core', 'core_noTWKO', 'cr2', 'mix', 'top30'], (10, 12, 15)):
            for lab, rule, kw in [('a banda10', 'a', dict(band=0.10)), ('a banda25', 'a', dict(band=0.25)),
                                  ('bN M30 g1 + banda50', 'b', dict(K=N, M=30, grace=1, rebal=True, band=0.5)),
                                  ('b K15 M30 g1', 'b', dict(K=15, M=30, grace=1))]:
                for tax in (True, False):
                    r = sim(CFG[lk](N), rule, ds, tax=tax, **kw)
                    rows.append(dict(lam=lam, periodo=p, lista=lk, N=N, cfg=lab, tasse=tax, irr=r['irr'], twr=r['twr'], ordini=r['orders'] / yrs,
                                     costi=(r['fees'] + r['spread']) / r['vmean'] / yrs, tasse_pct=r['taxpaid'] / r['vmean'] / yrs))
T = pd.DataFrame(rows)
base = T[T.cfg == 'a banda10'].set_index(['lam', 'periodo', 'lista', 'N', 'tasse'])
T['d'] = [r.irr - base.loc[(r.lam, r.periodo, r.lista, r.N, r.tasse)].irr for r in T.itertuples()]
T['t'] = [nwt(r.twr - base.loc[(r.lam, r.periodo, r.lista, r.N, r.tasse)].twr) for r in T.itertuples()]
T.drop(columns='twr').to_csv(f'{OUTD}/ist_06_variante.csv', index=False)
pd.set_option('display.width', 250)
for lam in (1.0, 1 / 3):
    X = T[(T.lam == lam) & T.tasse]
    print('lambda', round(lam, 2))
    print(X.pivot_table(index='cfg', columns='periodo', values='d').mul(100).round(1).to_string())
    print(X[X.periodo == '2018-26'].pivot_table(index='cfg', columns='lista', values='d').mul(100).round(1).to_string())
    print(X[X.periodo == '2018-26'].groupby('cfg')[['ordini', 'costi', 'tasse_pct', 't']].mean().round(3).to_string())
