# avv_ist_04: misto e Crescita senza TW/KO, regola consigliata contro oggi: t di Newey-West, lambda 1 e 1/3, 2018-26 e 2012-17.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
TW = set(F.t[TWKO])
for k in ['cr2', 'q3']:
    ic.ORD[k + '_nt'] = {d: [t for t in L if t not in TW] for d, L in ic.ORD[k].items()}
C = {'mix_nt': lambda N: [('core_noTWKO', 0.5, (N + 1) // 2), ('q3_nt', 0.5, N // 2)], 'cr2_nt': lambda N: [('cr2_nt', 1.0, N)]}
RET0 = ic.RET
for lam in (1.0, 1 / 3):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
    for p in ('2018-26', '2012-17'):
        ds = pdates(p); v = sim_vwce(ds)
        for lk, f in C.items():
            for N in (10, 12, 15, 20):
                r = sim(f(N), 'b', ds, K=N, M=30, grace=1); a = sim(f(N), 'a', ds)
                print(f"lam {lam:.2f} {p} {lk} N{N}: consigliata {r['irr']:.4f} oggi {a['irr']:.4f} diff {100 * (r['irr'] - a['irr']):+.1f} t {nwt(r['twr'] - a['twr']):.2f} | vs VWCE {100 * (r['irr'] - v['irr']):+.1f}")
