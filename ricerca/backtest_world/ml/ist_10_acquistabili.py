# ist_10 (correzioni dopo la verifica avversariale, 07/11): liste ACQUISTABILI su Trade Republic = senza Taiwan e Corea,
# tranne TSMC (2330.TW), che si compra come ADR americano TSM (rendimento e spread di 2330.TW usati come approssimazione).
# Per core, Crescita >= 2 Mld$, misto (8 core + 7 Qualita') e top 30, N 15:
#  (1) regola consigliata (K 15, M 30, uscita subito) contro oggi e contro VWCE, lordo/netto, lambda 1 e 1/3, per periodo;
#  (2) 2020 e 2025 neutralizzati (in quei trimestri ogni titolo rende come VWCE);
#  (3) quota del guadagno dei primi titoli; senza i 5 migliori;
#  (4) finestre di 3 anni divise fra partenze prima del 2018 e dal 2018;
#  (5) regole lente contro oggi (semestrale, annuale, attesa 2 trimestri, tesi 3 anni), anche senza 2020 e 2025;
#  (6) misto acquistabile, consigliata contro oggi per N 10-20;
#  (7) tasse: quota dovuta al realizzo continuo (VWCE ritoccato allo stesso rendimento lordo).
import sys, os, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
TWX = set(F.t[TWKO]) - {'2330.TW'}; TWA = set(F.t[TWKO])
ORD0 = {k: dict(v_) for k, v_ in ic.ORD.items()}
for k in ['core', 'cr2', 'q3', 'top30']:
    ic.ORD[k + '_tsm'] = {d: [t for t in L if t not in TWX] for d, L in ORD0[k].items()}
    ic.ORD[k + '_nt'] = {d: [t for t in L if t not in TWA] for d, L in ORD0[k].items()}
    ic.BADSET[k + '_tsm'] = ic.BADSET[k]; ic.BADSET[k + '_nt'] = ic.BADSET[k]
C = {'core': CFG['core'], 'cr2': CFG['cr2'], 'mix': CFG['mix'], 'top30': CFG['top30'],
     'core_tsm': lambda N: [('core_tsm', 1.0, N)], 'cr2_tsm': lambda N: [('cr2_tsm', 1.0, N)],
     'mix_tsm': lambda N: [('core_tsm', 0.5, (N + 1) // 2), ('q3_tsm', 0.5, N // 2)], 'top30_tsm': lambda N: [('top30_tsm', 1.0, N)],
     'core_nt': lambda N: [('core_nt', 1.0, N)], 'cr2_nt': lambda N: [('cr2_nt', 1.0, N)],
     'mix_nt': lambda N: [('core_nt', 0.5, (N + 1) // 2), ('q3_nt', 0.5, N // 2)], 'top30_nt': lambda N: [('top30_nt', 1.0, N)]}
BUY = ['core_tsm', 'cr2_tsm', 'mix_tsm', 'top30_tsm']
REC = dict(K=15, M=30, grace=1)
RET0 = ic.RET; VW0 = ic.VW.copy()
def set_lambda(lam):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
def mdd(r):
    w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()

# ---------------------------------------------------------------- (1) tabella principale
rows = []
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for p in PER:
        ds = pdates(p); yrs = (NXT[ds[-1]] - ds[0]).days / 365.25
        for tax in ((True, False) if p == '2018-26' else (True,)):
            v = sim_vwce(ds, tax=tax)
            for lk in C:
                r = sim(C[lk](15), 'b', ds, tax=tax, **REC); a = sim(C[lk](15), 'a', ds, tax=tax)
                rows.append(dict(lam=round(lam, 2), periodo=p, tasse=tax, lista=lk, irr=r['irr'], irr_oggi=a['irr'], vwce=v['irr'],
                                 d_oggi=r['irr'] - a['irr'], t_oggi=nwt(r['twr'] - a['twr']), d_vwce=r['irr'] - v['irr'], t_vwce=nwt(r['twr'] - v['twr']),
                                 W=r['W'], W_vwce=v['W'], mdd=mdd(r['twr']), mdd_vwce=mdd(v['twr']), ordini=r['orders'] / yrs, ordini_oggi=a['orders'] / yrs,
                                 costi=(r['fees'] + r['spread']) / r['vmean'] / yrs, costi_oggi=(a['fees'] + a['spread']) / a['vmean'] / yrs,
                                 tasse_pct=r['taxpaid'] / r['vmean'] / yrs))
T = pd.DataFrame(rows); T.to_csv(f'{OUTD}/ist_10_acquistabili.csv', index=False)
print('=== (1) 2018-26, N 15, regola consigliata')
for lam in (1.0, 0.33):
    X = T[(T.lam == lam) & (T.periodo == '2018-26')]
    g = X[~X.tasse].set_index('lista').irr
    Y = X[X.tasse].set_index('lista')
    Y = Y.assign(lordo=g)
    print('lambda', lam, 'VWCE netto', round(Y.vwce.iloc[0] * 100, 1), 'lordo', round(X[~X.tasse].vwce.iloc[0] * 100, 1), 'W', round(Y.W_vwce.iloc[0]), 'mdd', round(Y.mdd_vwce.iloc[0] * 100))
    print(pd.DataFrame({'lordo': Y.lordo * 100, 'netto': Y.irr * 100, 'oggi': Y.irr_oggi * 100, 'd_oggi': Y.d_oggi * 100, 't_oggi': Y.t_oggi,
                        'd_vwce': Y.d_vwce * 100, 't_vwce': Y.t_vwce, 'W': Y.W, 'mdd': Y.mdd * 100, 'ordini': Y.ordini, 'ordini_oggi': Y.ordini_oggi,
                        'costi': Y.costi * 100, 'costi_oggi': Y.costi_oggi * 100, 'tasse_pct': Y.tasse_pct * 100}).round(2).to_string())
    Z = T[(T.lam == lam) & T.tasse]
    print(Z.pivot_table(index='lista', columns='periodo', values=['d_vwce', 'd_oggi'], sort=False).mul(100).round(1).to_string())
    print('VWCE per periodo', Z.groupby('periodo').vwce.first().mul(100).round(1).to_dict())

# ---------------------------------------------------------------- (2) 2020 e 2025 neutralizzati (lambda 1)
print('=== (2) neutralizzati, 2018-26, lambda 1')
ds = pdates('2018-26')
Q20 = [d for d in REB if pd.Timestamp('2019-12-31') <= d <= pd.Timestamp('2020-09-30')]
Q25 = [d for d in REB if pd.Timestamp('2024-12-31') <= d <= pd.Timestamp('2025-09-30')]
for lab, qs in [('nessuno', []), ('2020', Q20), ('2025', Q25), ('2020+2025', Q20 + Q25)]:
    ic.RET = {d: ({t: VW0[d] for t in R} if d in qs else R) for d, R in RET0.items()}
    v = sim_vwce(ds); s = []
    for lk in ['core'] + BUY + ['core_nt']:
        r = sim(C[lk](15), 'b', ds, **REC); a = sim(C[lk](15), 'a', ds)
        s.append(f"{lk} vsVWCE {100 * (r['irr'] - v['irr']):+.1f} vsOggi {100 * (r['irr'] - a['irr']):+.1f}")
    print(f"{lab}: " + ' | '.join(s))
ic.RET = RET0

# ---------------------------------------------------------------- (3) guadagno per titolo
print('=== (3) primi titoli, 2018-26, lambda 1, lordo di tasse')
PNL = {}
class TBook(ic.Book):
    def sell(s, t, frac=1.0, d=None, free=False):
        c0 = s.cash; tp0 = s.taxpaid; super().sell(t, frac, d, free); PNL[t] = PNL.get(t, 0.0) + (s.cash - c0) + (s.taxpaid - tp0)
    def buy(s, t, amt, d, sleeve=0):
        c0 = s.cash; super().buy(t, amt, d, sleeve); PNL[t] = PNL.get(t, 0.0) + (s.cash - c0)
BK0 = ic.Book
v = sim_vwce(ds)
for lk in ['core'] + BUY:
    ic.Book = TBook; PNL.clear(); sim(C[lk](15), 'b', ds, tax=False, **REC); ic.Book = BK0
    P = pd.Series(PNL).sort_values(ascending=False); tot = P.sum()
    ntw = sum(1 for t in P.head(10).index if t in TWA)
    line = (f"{lk}: guadagno {tot:,.0f} EUR su {len(P)} titoli; primi 5: " + ', '.join(f"{t} {x:,.0f}" for t, x in P.head(5).items())
            + f"; primi 3 {P.head(3).sum() / tot:.0%}, primi 5 {P.head(5).sum() / tot:.0%}, primi 10 {P.head(10).sum() / tot:.0%}; taiwanesi/coreani nei primi 10: {ntw}")
    drop = set(P.head(5).index); saved = dict(ic.ORD)
    for kk in list(ic.ORD): ic.ORD[kk] = {d: [t for t in L if t not in drop] for d, L in saved[kk].items()}
    rr = sim(C[lk](15), 'b', ds, **REC)
    ic.ORD.clear(); ic.ORD.update(saved)
    print(line + f" | senza i primi 5: contro VWCE {100 * (rr['irr'] - v['irr']):+.1f}")

# ---------------------------------------------------------------- (4) finestre di 3 anni
print('=== (4) finestre di 3 anni (12 trimestri), partenze prima del 2018 e dal 2018')
WIN = [w for w in [REB[i:i + 12] for i in range(len(REB) - 11)] if w[-1] <= pd.Timestamp('2026-09-30')]
win = []
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for w in WIN:
        v = sim_vwce(w)
        for lk in ['core'] + BUY:
            r = sim(C[lk](15), 'b', w, **REC); a = sim(C[lk](15), 'a', w)
            win.append(dict(lam=round(lam, 2), lista=lk, inizio=w[0], d_oggi=r['irr'] - a['irr'], d_vwce=r['irr'] - v['irr']))
ic.RET = RET0
Wd = pd.DataFrame(win); Wd['dal2018'] = Wd.inizio >= pd.Timestamp('2017-12-31'); Wd.to_csv(f'{OUTD}/ist_10_finestre.csv', index=False)
print(Wd.groupby(['lam', 'lista', 'dal2018']).agg(n=('d_vwce', 'size'), batte_oggi=('d_oggi', lambda s: (s > 0).mean() * 100),
      med=('d_vwce', lambda s: s.median() * 100), batte_vw=('d_vwce', lambda s: (s > 0).mean() * 100),
      p10=('d_vwce', lambda s: s.quantile(.1) * 100), p90=('d_vwce', lambda s: s.quantile(.9) * 100)).round(1).to_string())
print('tutte le partenze:')
print(Wd.groupby(['lam', 'lista']).agg(batte_oggi=('d_oggi', lambda s: (s > 0).mean() * 100), med=('d_vwce', lambda s: s.median() * 100),
      batte_vw=('d_vwce', lambda s: (s > 0).mean() * 100)).round(1).to_string())

# ---------------------------------------------------------------- (5) regole lente contro oggi, N 15
print('=== (5) regole lente contro oggi, N 15, netto')
SLOW = [('ogni 6 mesi', 'a', dict(freq=2)), ('ogni anno', 'a', dict(freq=4)), ('attesa 2 trim. K10 M30', 'b', dict(K=10, M=30, grace=2)),
        ('attesa 2 trim. K15 M40', 'b', dict(K=15, M=40, grace=2)), ('tesi 3 anni', 'c', dict(X=3))]
srows = []
for lab0, lam, p, qs in [('storico', 1.0, '2018-26', []), ('storico', 1.0, '2012-17', []), ('senza 2020+2025', 1.0, '2018-26', Q20 + Q25),
                         ('realistico', 1 / 3, '2018-26', [])]:
    set_lambda(lam)
    if qs: ic.RET = {d: ({t: VW0[d] for t in R} if d in qs else R) for d, R in ic.RET.items()}
    q = pdates(p)
    for lk in ['core'] + BUY:
        a = sim(C[lk](15), 'a', q)
        for lab, rule, kw in SLOW:
            r = sim(C[lk](15), rule, q, **kw)
            srows.append(dict(caso=f'{lab0} {p}', lista=lk, regola=lab, d=100 * (r['irr'] - a['irr']), t=nwt(r['twr'] - a['twr'])))
ic.RET = RET0
S = pd.DataFrame(srows); S.to_csv(f'{OUTD}/ist_10_lente.csv', index=False)
print(S.pivot_table(index=['caso', 'regola'], columns='lista', values='d', sort=False).round(1).to_string())
print(S.pivot_table(index=['caso', 'regola'], columns='lista', values='t', sort=False).round(2).to_string())
print('media acquistabili:'); print(S[S.lista.isin(BUY)].pivot_table(index='regola', columns='caso', values='d', sort=False).round(1).to_string())

# ---------------------------------------------------------------- (6) misto acquistabile, N 10-20
print('=== (6) misto e Crescita acquistabili: consigliata (K = N, M 30) contro oggi')
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for p in ('2018-26', '2012-17'):
        q = pdates(p); v = sim_vwce(q)
        for lk in ('mix_tsm', 'cr2_tsm'):
            s = []
            for N in (10, 12, 15, 20):
                r = sim(C[lk](N), 'b', q, K=N, M=30, grace=1); a = sim(C[lk](N), 'a', q)
                s.append(f"N{N} {100 * (r['irr'] - a['irr']):+.1f} (t {nwt(r['twr'] - a['twr']):.2f}, vsVWCE {100 * (r['irr'] - v['irr']):+.1f})")
            print(f"lam {lam:.2f} {p} {lk}: " + ' | '.join(s))
ic.RET = RET0

# ---------------------------------------------------------------- (7) tasse: realizzo continuo
print('=== (7) tasse con vantaggio realistico, 2018-26')
set_lambda(1 / 3)
for lk in ['core', 'core_tsm', 'mix_tsm']:
    cg = sim(C[lk](15), 'b', ds, tax=False, **REC); cn = sim(C[lk](15), 'b', ds, **REC)
    lo, hi = -0.05, 0.05
    for _ in range(60):
        x = (lo + hi) / 2; ic.VW = (1 + VW0) * (1 + x) - 1
        if sim_vwce(ds, tax=False)['irr'] < cg['irr']: lo = x
        else: hi = x
    vg2 = sim_vwce(ds, tax=False); vn2 = sim_vwce(ds); ic.VW = VW0
    vg = sim_vwce(ds, tax=False); vn = sim_vwce(ds)
    print(f"{lk}: lordo {cg['irr'] * 100:.1f} netto {cn['irr'] * 100:.1f} tasse {100 * (cg['irr'] - cn['irr']):.1f} | VWCE allo stesso lordo: tasse "
          f"{100 * (vg2['irr'] - vn2['irr']):.1f} -> realizzo continuo {100 * ((cg['irr'] - cn['irr']) - (vg2['irr'] - vn2['irr'])):.1f} | VWCE vero tasse {100 * (vg['irr'] - vn['irr']):.1f}")
ic.RET = RET0
