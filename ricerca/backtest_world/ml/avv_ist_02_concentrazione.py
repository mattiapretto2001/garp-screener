# avv_ist_02: (1) guadagno per titolo (lordo di tasse) nella regola consigliata, core e core senza TW/KO: quanto pesano i primi nomi;
# rifaccio senza i 3 / 5 nomi migliori; (2) neutralizzo il 2020 e il 2025 (in quei trimestri ogni titolo rende come VWCE);
# (3) misto e Crescita senza TW/KO nel 2012-17 e nei sottoperiodi; (4) finestre di 3 anni: partenze prima e dopo il 2018.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
REC = dict(K=15, M=30, grace=1)
ds = pdates('2018-26')
TW = set(F.t[TWKO]); ORD0 = {k: dict(v_) for k, v_ in ic.ORD.items()}
for k in ['cr2', 'q3', 'top30']:
    ic.ORD[k + '_nt'] = {d: [t for t in L if t not in TW] for d, L in ORD0[k].items()}
CFGX = {'core': CFG['core'], 'core_noTWKO': CFG['core_noTWKO'], 'mix': CFG['mix'], 'cr2': CFG['cr2'],
        'mix_nt': lambda N: [('core_noTWKO', 0.5, 8), ('q3_nt', 0.5, 7)], 'cr2_nt': lambda N: [('cr2_nt', 1.0, N)]}

# ---- 1. guadagno per titolo: Book strumentato
PNL = {}
class TBook(ic.Book):
    def sell(s, t, frac=1.0, d=None, free=False):
        c0 = s.cash; tp0 = s.taxpaid
        super().sell(t, frac, d, free)
        PNL[t] = PNL.get(t, 0.0) + (s.cash - c0) + (s.taxpaid - tp0)   # incasso prima delle tasse
    def buy(s, t, amt, d, sleeve=0):
        c0 = s.cash; super().buy(t, amt, d, sleeve); PNL[t] = PNL.get(t, 0.0) + (s.cash - c0)
BK0 = ic.Book; ic.Book = TBook
v = sim_vwce(ds)
for lk in ['core', 'core_noTWKO', 'mix_nt', 'cr2']:
    PNL.clear(); r = sim(CFGX[lk](15), 'b', ds, tax=False, **REC)
    P = pd.Series(PNL).sort_values(ascending=False); tot = P.sum()
    print(f"{lk}: guadagno lordo totale {tot:,.0f} EUR su {len(P)} titoli; primi 5: " +
          ', '.join(f"{t} {x:,.0f}" for t, x in P.head(5).items()) + f"; quota primi 3 {P.head(3).sum() / tot:.0%}, primi 5 {P.head(5).sum() / tot:.0%}, primi 10 {P.head(10).sum() / tot:.0%}")
    for k in (3, 5):
        drop = set(P.head(k).index)
        saved = {kk: ic.ORD[kk] for kk in ic.ORD}
        for kk in list(ic.ORD): ic.ORD[kk] = {d: [t for t in L if t not in drop] for d, L in saved[kk].items()}
        ic.Book = BK0
        rr = sim(CFGX[lk](15), 'b', ds, **REC)
        ic.Book = TBook
        for kk in saved: ic.ORD[kk] = saved[kk]
        print(f"   senza i primi {k}: netto {rr['irr']:.4f}, contro VWCE {rr['irr'] - v['irr']:+.4f}")
ic.Book = BK0

# ---- 2. neutralizzare 2020 e 2025
RET0 = ic.RET; VW0 = ic.VW
Q20 = [d for d in REB if pd.Timestamp('2019-12-31') <= d <= pd.Timestamp('2020-09-30')]
Q25 = [d for d in REB if pd.Timestamp('2024-12-31') <= d <= pd.Timestamp('2025-09-30')]
for lab, qs in [('nessuno', []), ('2020', Q20), ('2025', Q25), ('2020+2025', Q20 + Q25)]:
    ic.RET = {d: ({t: VW0[d] for t in R} if d in qs else R) for d, R in RET0.items()}
    v = sim_vwce(ds); s = []
    for lk in ['core', 'core_noTWKO', 'mix', 'mix_nt', 'cr2', 'cr2_nt']:
        r = sim(CFGX[lk](15), 'b', ds, **REC); a = sim(CFGX[lk](15), 'a', ds); f4 = sim(CFGX[lk](15), 'a', ds, freq=4)
        s.append(f"{lk} vsVWCE {100 * (r['irr'] - v['irr']):+.1f} vsOggi {100 * (r['irr'] - a['irr']):+.1f} annuale {100 * (f4['irr'] - a['irr']):+.1f}")
    print(f"neutralizzato {lab}: VWCE {v['irr']:.4f} | " + ' | '.join(s))
ic.RET = RET0

# ---- 3. sottoperiodi delle liste senza TW/KO
for p in ['2012-17', '2018-21', '2022-24', '2025-26']:
    q = pdates(p); v = sim_vwce(q); s = []
    for lk in ['core', 'core_noTWKO', 'mix', 'mix_nt', 'cr2', 'cr2_nt']:
        r = sim(CFGX[lk](15), 'b', q, **REC); a = sim(CFGX[lk](15), 'a', q)
        s.append(f"{lk} vsVWCE {100 * (r['irr'] - v['irr']):+.1f} vsOggi {100 * (r['irr'] - a['irr']):+.1f}")
    print(p, f"VWCE {v['irr']:.4f} | " + ' | '.join(s))

# ---- 4. finestre di 3 anni, divise per partenza prima/dopo il 31/12/2017 (prima del 2018 mancano i delistati)
W = pd.read_csv(f'{OUTD}/ist_08_finestre.csv', parse_dates=['inizio'])
W['dopo2018'] = W.inizio >= pd.Timestamp('2017-12-31')
print(W.groupby(['lam', 'lista', 'dopo2018']).d_vwce.agg(['count', 'median', lambda s: (s > 0).mean()]).round(3).to_string())
