# avv_ist_03: (1) "chi esce perde subito il vantaggio": differenza trimestrale (dentro la lista, posti 1-30) - (uscito da 1 trimestre),
# media per trimestre e t di Newey-West sulla serie di 35 trimestri (non sulle righe titolo-trimestre, che sono correlate);
# (2) regole lente (attesa 2 trimestri, tesi a 3 anni) dopo aver neutralizzato 2020 e 2025.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
for lk in ['core', 'core_noTWKO', 'cr2', 'q3']:
    for p in ['2018-26', '2012-17']:
        diff, inl, ex1 = [], [], []
        for d in pdates(p):
            L = ORD[lk].get(d, []); R = RET.get(d, {}); u = UNIV_EW[d]; j0 = REB.index(d)
            prev = set(ORD[lk].get(REB[j0 - 1], [])) if j0 else set()
            a = [R[t] - u for t in L[:30] if t in R]
            b = [R[t] - u for t in prev - set(L) if t in R]
            if a and b: diff.append(np.mean(a) - np.mean(b)); inl.append(np.mean(a)); ex1.append(np.mean(b))
        diff = np.array(diff)
        print(f"{lk:12s} {p}: trimestri {len(diff)}, dentro {np.mean(inl) * 400:+.1f}, uscito1 {np.mean(ex1) * 400:+.1f} pt/anno (x4 semplice); "
              f"differenza {diff.mean() * 400:+.1f} t NW {nwt(diff):.2f}; trimestri con differenza > 0: {np.mean(diff > 0):.0%}")
ds = pdates('2018-26')
RET0 = ic.RET; VW0 = ic.VW
Q = [d for d in REB if pd.Timestamp('2019-12-31') <= d <= pd.Timestamp('2020-09-30') or pd.Timestamp('2024-12-31') <= d <= pd.Timestamp('2025-09-30')]
for lab, qs in [('nessuno', []), ('2020+2025', Q)]:
    ic.RET = {d: ({t: VW0[d] for t in R} if d in qs else R) for d, R in RET0.items()}
    for lk in ['core', 'core_noTWKO', 'mix']:
        a = sim(CFG[lk](15), 'a', ds)
        g2 = sim(CFG[lk](15), 'b', ds, K=15, M=40, grace=2); c3 = sim(CFG[lk](15), 'c', ds, X=3); f2 = sim(CFG[lk](15), 'a', ds, freq=2)
        print(f"neutralizzato {lab} {lk:12s}: attesa 2 trim. {100 * (g2['irr'] - a['irr']):+.1f}, tesi 3 anni {100 * (c3['irr'] - a['irr']):+.1f}, semestrale {100 * (f2['irr'] - a['irr']):+.1f}")
ic.RET = RET0
