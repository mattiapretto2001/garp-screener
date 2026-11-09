# ist_09: controlli finali: (1) top 30 "intera" = N 30 (non tutta la classifica GARP >= 2 Mld$); (2) spread doppio
# (0,2% / 0,6%) per regola consigliata e regola di oggi, N 15; lambda 1 e 1/3, netto.
import sys, os, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
RET0 = ic.RET; SPR0 = {d: dict(x) for d, x in ic.SPR.items()}
def set_lambda(lam):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
rows = []
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for p in ('2018-26', '2012-17'):
        ds = pdates(p); yrs = (NXT[ds[-1]] - ds[0]).days / 365.25
        r = sim(CFG['top30'](30), 'a', ds, band=0.10)
        rows.append(dict(prova='top 30 intera (N 30, oggi)', lam=lam, periodo=p, lista='top30', irr=r['irr'], ordini=r['orders'] / yrs, nhold=r['nhold']))
        for k in (1, 2):
            for d in ic.SPR: ic.SPR[d] = {t: s * k for t, s in SPR0[d].items()}
            for lk in ['core', 'core_noTWKO', 'cr2', 'mix', 'top30']:
                a = sim(CFG[lk](15), 'a', ds, band=0.10); b = sim(CFG[lk](15), 'b', ds, K=15, M=30, grace=1)
                rows.append(dict(prova=f'spread x{k}', lam=lam, periodo=p, lista=lk, irr=b['irr'], irr_oggi=a['irr'], d=b['irr'] - a['irr'],
                                 costi=(b['fees'] + b['spread']) / b['vmean'] / yrs, costi_oggi=(a['fees'] + a['spread']) / a['vmean'] / yrs))
        for d in ic.SPR: ic.SPR[d] = dict(SPR0[d])
T = pd.DataFrame(rows); T.to_csv(f'{OUTD}/ist_09_controlli.csv', index=False)
pd.set_option('display.width', 220)
print(T[T.prova.str.startswith('top')].round(3).to_string())
S = T[T.prova.str.startswith('spread')]
print(S.groupby(['prova', 'lam', 'periodo'])[['d', 'irr', 'irr_oggi', 'costi', 'costi_oggi']].mean().mul(100).round(2).to_string())
# tesi (c X3) e controllo annuale nel core con vantaggio realistico, N 10/12/15
set_lambda(1 / 3); ds = pdates('2018-26')
for lk in ('core', 'core_noTWKO', 'mix'):
    v = [sim(CFG[lk](N), 'c', ds, X=3)['irr'] - sim(CFG[lk](N), 'a', ds)['irr'] for N in (10, 12, 15)]
    print(lk, 'tesi X3 contro oggi, realistico 2018-26:', np.round(np.array(v) * 100, 1), 'media', round(np.mean(v) * 100, 1))
