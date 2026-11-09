# avv_ist_01 (verifica avversariale di R_isteresi_dimensione): (1) rifaccio 3+ numeri; (2) liste senza Taiwan e Corea
# anche per misto, Crescita e top 30; (3) universo GARP a pesi uguali contro VWCE (ancora del "vantaggio realistico");
# (4) scomposizione del divario fiscale contro VWCE.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
REC = dict(K=15, M=30, grace=1)
ds = pdates('2018-26'); yrs = (NXT[ds[-1]] - ds[0]).days / 365.25
out = []
print('=== 1. riproduzione, 2018-26 netto, N 15')
v = sim_vwce(ds); vg = sim_vwce(ds, tax=False)
print(f"VWCE netto {v['irr']:.4f} lordo {vg['irr']:.4f} W {v['W']:.0f} versato {v['contrib']:.0f}")
o_rec, o_a, o_f4 = [], [], []
for lk in ['core', 'core_noTWKO', 'cr2', 'mix', 'top30']:
    r = sim(CFG[lk](15), 'b', ds, **REC); a = sim(CFG[lk](15), 'a', ds); f4 = sim(CFG[lk](15), 'a', ds, freq=4)
    rg = sim(CFG[lk](15), 'b', ds, tax=False, **REC)
    o_rec.append(r['orders'] / yrs); o_a.append(a['orders'] / yrs); o_f4.append(f4['irr'] - a['irr'])
    print(f"{lk:12s} cons. netto {r['irr']:.4f} lordo {rg['irr']:.4f} W {r['W']:.0f} | oggi {a['irr']:.4f} diff {r['irr'] - a['irr']:+.4f} t {nwt(r['twr'] - a['twr']):.2f}"
          f" | vs VWCE {r['irr'] - v['irr']:+.4f} | ordini/anno {r['orders'] / yrs:.1f} vs {a['orders'] / yrs:.1f} | costi {(r['fees'] + r['spread']) / r['vmean'] / yrs:.4f}"
          f" vs {(a['fees'] + a['spread']) / a['vmean'] / yrs:.4f} | rotazione {r['traded'] / 2 / yrs / r['vmean']:.2f} | annuale-oggi {f4['irr'] - a['irr']:+.4f}")
print(f"media ordini: consigliata {np.mean(o_rec):.1f}, oggi {np.mean(o_a):.1f}; annuale contro oggi (N 15, media liste) {np.mean(o_f4):+.4f}")

print('=== 2. senza Taiwan e Corea anche per misto, Crescita, top 30 (lambda 1 e 1/3)')
TW = set(F.t[TWKO])
ORD0 = {k: dict(v_) for k, v_ in ic.ORD.items()}
for k in ['cr2', 'q3', 'top30']:
    ic.ORD[k + '_nt'] = {d: [t for t in L if t not in TW] for d, L in ORD0[k].items()}
CFG2 = {'core_noTWKO': lambda N: [('core_noTWKO', 1.0, N)], 'cr2_nt': lambda N: [('cr2_nt', 1.0, N)],
        'mix_nt': lambda N: [('core_noTWKO', 0.5, 8), ('q3_nt', 0.5, 7)], 'top30_nt': lambda N: [('top30_nt', 1.0, N)],
        'mix': CFG['mix'], 'cr2': CFG['cr2'], 'top30': CFG['top30']}
RET0 = ic.RET
for lam in (1.0, 1 / 3):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
    for lk, f in CFG2.items():
        r = sim(f(15), 'b', ds, **REC); a = sim(f(15), 'a', ds)
        print(f"lam {lam:.2f} {lk:12s} netto {r['irr']:.4f} vs VWCE {r['irr'] - v['irr']:+.4f} (t {nwt(r['twr'] - v['twr']):.2f}) vs oggi {r['irr'] - a['irr']:+.4f} W {r['W']:.0f}")
ic.RET = RET0

print('=== 3. universo GARP a pesi uguali (ancora del lambda) contro VWCE, rendimento composto annuo')
u = UNIV_EW[ds]; w = VW[ds]
print(f"universo EW {ann_twr(u):.4f}  VWCE {ann_twr(w):.4f}")
for p in ('2012-17', '2018-21', '2022-24', '2025-26'):
    q = pdates(p); print(p, f"universo {ann_twr(UNIV_EW[q]):.4f} VWCE {ann_twr(VW[q]):.4f}")

print('=== 4. divario fiscale: VWCE con lo stesso rendimento lordo del core realistico')
VW0 = ic.VW.copy()
ic.RET = {d: {t: UNIV_EW[d] + (r - UNIV_EW[d]) / 3 for t, r in R.items()} for d, R in RET0.items()}
cg = sim(CFG['core'](15), 'b', ds, tax=False, **REC); cn = sim(CFG['core'](15), 'b', ds, **REC)
ic.RET = RET0
lo, hi = -0.05, 0.05
for _ in range(60):
    x = (lo + hi) / 2; ic.VW = (1 + VW0) * (1 + x) - 1
    g = sim_vwce(ds, tax=False)['irr']
    if g < cg['irr']: lo = x
    else: hi = x
vg2 = sim_vwce(ds, tax=False); vn2 = sim_vwce(ds)
ic.VW = VW0
print(f"core realistico lordo {cg['irr']:.4f} netto {cn['irr']:.4f} -> tasse {cg['irr'] - cn['irr']:.4f}")
print(f"VWCE ritoccato allo stesso lordo {vg2['irr']:.4f} netto {vn2['irr']:.4f} -> tasse {vg2['irr'] - vn2['irr']:.4f}")
print(f"VWCE vero: lordo {vg['irr']:.4f} netto {v['irr']:.4f} -> tasse {vg['irr'] - v['irr']:.4f}")
