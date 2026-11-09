# avv_ist_05: TSMC si compra su Trade Republic come ADR americano (TSM): core senza Taiwan e Corea ma con 2330.TW, lambda 1 e 1/3;
# quota del guadagno del core da Taiwan e Corea.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
TW = set(F.t[TWKO]) - {'2330.TW'}
ic.ORD['core_tsm'] = {d: [t for t in L if t not in TW] for d, L in ic.ORD['core'].items()}
for k in ['q3']:
    ic.ORD[k + '_tsm'] = {d: [t for t in L if t not in TW] for d, L in ic.ORD[k].items()}
ds = pdates('2018-26'); v = sim_vwce(ds); RET0 = ic.RET
for lam in (1.0, 1 / 3):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
    for lab, sl in [('core con TSMC', [('core_tsm', 1.0, 15)]), ('misto con TSMC', [('core_tsm', 0.5, 8), ('q3_tsm', 0.5, 7)])]:
        r = sim(sl, 'b', ds, K=15, M=30, grace=1)
        print(f"lam {lam:.2f} {lab}: netto {r['irr']:.4f} vs VWCE {100 * (r['irr'] - v['irr']):+.1f}")
