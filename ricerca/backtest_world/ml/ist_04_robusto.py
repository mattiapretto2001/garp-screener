# ist_04: (1) vantaggio "realistico": i rendimenti di ogni titolo sono ridotti verso l'universo GARP a pesi uguali,
#   r' = U + lambda (r - U), lambda = 1/3 (il vantaggio atteso delle liste e' circa un terzo di quello 2018-26);
# (2) finestre mobili di 3 anni (12 trimestri), una per ogni trimestre di partenza 2011-12 .. 2023-09, ognuna con 9.500 EUR
#   iniziali e 3.000 EUR a trimestre: quante volte una regola batte quella di oggi e quante volte la lista batte VWCE.
import sys, os, pickle, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
RET0 = ic.RET
def set_lambda(lam):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
SEL = [('a', dict(freq=1)), ('a', dict(freq=2)), ('a', dict(freq=4)), ('a2', dict(freq=1)), ('b', dict(K=15, M=30, grace=1)),
       ('b', dict(K=10, M=30, grace=2)), ('b', dict(K=15, M=40, grace=2)), ('c', dict(X=3))]
def lab(rule, kw):
    if rule == 'a': return f"a f{kw['freq']}"
    if rule == 'a2': return 'a2'
    if rule == 'b': return f"b K{kw['K']} M{kw['M']} g{kw['grace']}"
    return f"c X{kw['X']}"
WIN = [REB[i:i + 12] for i in range(len(REB) - 11)]
WIN = [w for w in WIN if w[-1] <= pd.Timestamp('2026-09-30')]
rows = []
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for lk, N, (rule, kw) in itertools.product(['core', 'core_noTWKO', 'cr2', 'mix', 'top30'], (10, 12, 15), SEL):
        for p in ('2018-26', '2012-17'):
            for tax in (True, False):
                r = sim(CFG[lk](N), rule, pdates(p), tax=tax, **kw)
                rows.append(dict(lam=lam, lista=lk, N=N, cfg=lab(rule, kw), finestra=p, tasse=tax, irr=r['irr'], W=r['W'],
                                 costi=(r['fees'] + r['spread']) / r['vmean'] / ((NXT[pdates(p)[-1]] - pdates(p)[0]).days / 365.25)))
        for w in WIN:
            r = sim(CFG[lk](N), rule, w, tax=True, **kw)
            rows.append(dict(lam=lam, lista=lk, N=N, cfg=lab(rule, kw), finestra=w[0].strftime('%Y-%m'), tasse=True, irr=r['irr'], W=r['W'], costi=np.nan))
    print('lambda', lam, 'fatto', flush=True)
for p in ('2018-26', '2012-17'):
    for tax in (True, False):
        v = sim_vwce(pdates(p), tax=tax); rows.append(dict(lam=0, lista='VWCE', N=0, cfg='VWCE', finestra=p, tasse=tax, irr=v['irr'], W=v['W']))
for w in WIN:
    v = sim_vwce(w, tax=True); rows.append(dict(lam=0, lista='VWCE', N=0, cfg='VWCE', finestra=w[0].strftime('%Y-%m'), tasse=True, irr=v['irr'], W=v['W']))
T = pd.DataFrame(rows); T.to_csv(f'{OUTD}/ist_04_robusto.csv', index=False)
print(len(T), 'righe; finestre', len(WIN))
