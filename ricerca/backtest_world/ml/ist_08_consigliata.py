# ist_08: numeri finali della regola consigliata (trimestrale, N 15, K 15, M 30, uscita subito, niente riequilibrio,
# versamenti al piu' sottopesato) contro oggi (a, N 15) e VWCE: per lista, lordo/netto, lambda 1 e 1/3, t NW, finestre di 3 anni,
# costi del primo anno in euro (partenza 2018, 2022, 2025).
import sys, os, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ist_common as ic
from ist_common import *
RET0 = ic.RET
def set_lambda(lam):
    ic.RET = {d: {t: UNIV_EW[d] + lam * (r - UNIV_EW[d]) for t, r in R.items()} for d, R in RET0.items()}
REC = ('b', dict(K=15, M=30, grace=1)); TODAY_ = ('a', dict(band=0.10))
LISTS = ['core', 'core_noTWKO', 'cr2', 'mix', 'top30']
rows, win = [], []
WIN = [w for w in [REB[i:i + 12] for i in range(len(REB) - 11)] if w[-1] <= pd.Timestamp('2026-09-30')]
for lam in (1.0, 1 / 3):
    set_lambda(lam)
    for p in PER:
        ds = pdates(p)
        for tax in (True, False):
            v = sim_vwce(ds, tax=tax)
            for lk in LISTS:
                r = sim(CFG[lk](15), REC[0], ds, tax=tax, **REC[1]); a = sim(CFG[lk](15), TODAY_[0], ds, tax=tax, **TODAY_[1])
                rows.append(dict(lam=lam, periodo=p, tasse=tax, lista=lk, irr=r['irr'], irr_oggi=a['irr'], vwce=v['irr'], d_oggi=r['irr'] - a['irr'],
                                 t_oggi=nwt(r['twr'] - a['twr']), d_vwce=r['irr'] - v['irr'], t_vwce=nwt(r['twr'] - v['twr']),
                                 W=r['W'], W_vwce=v['W'], versato=r['contrib']))
    for w in WIN:
        v = sim_vwce(w)
        for lk in LISTS:
            r = sim(CFG[lk](15), REC[0], w, **REC[1]); a = sim(CFG[lk](15), TODAY_[0], w, **TODAY_[1])
            win.append(dict(lam=lam, lista=lk, inizio=w[0], d_oggi=r['irr'] - a['irr'], d_vwce=r['irr'] - v['irr']))
T = pd.DataFrame(rows); T.to_csv(f'{OUTD}/ist_08_consigliata.csv', index=False)
Wd = pd.DataFrame(win); Wd.to_csv(f'{OUTD}/ist_08_finestre.csv', index=False)
pd.set_option('display.width', 250)
for lam in (1.0, 1 / 3):
    X = T[(T.lam == lam)]
    print('lambda', round(lam, 2))
    print(X.pivot_table(index=['lista', 'tasse'], columns='periodo', values='irr').mul(100).round(1).to_string())
    print(X[X.tasse].pivot_table(index='lista', columns='periodo', values=['d_oggi', 'd_vwce']).mul(100).round(1).to_string())
    print(X[X.tasse & (X.periodo == '2018-26')][['lista', 't_oggi', 't_vwce', 'W', 'W_vwce']].round(2).to_string())
    print(X[(X.periodo == '2018-26')].groupby('tasse')[['vwce']].first())
    Y = Wd[Wd.lam == lam]
    print(Y.groupby('lista').agg(oggi_med=('d_oggi', 'median'), batte_oggi=('d_oggi', lambda s: (s > 0).mean()), vw_med=('d_vwce', 'median'),
                                 batte_vw=('d_vwce', lambda s: (s > 0).mean()), p10=('d_vwce', lambda s: s.quantile(.1)), p90=('d_vwce', lambda s: s.quantile(.9))).mul(100).round(1).to_string())
# costi del primo anno (4 trimestri) partendo con 9.500 EUR
set_lambda(1.0)
for start in ('2018-03-31', '2021-12-31', '2024-12-31'):
    ds = [d for d in REB if d >= pd.Timestamp(start)][:4]
    for lk in ('core', 'core_noTWKO', 'mix'):
        r = sim(CFG[lk](15), REC[0], ds, liquidate=False, **REC[1]); a = sim(CFG[lk](15), TODAY_[0], ds, liquidate=False, **TODAY_[1])
        print(f'primo anno da {start} {lk}: consigliata ordini {r["orders"]}, commissioni {r["fees"]:.0f}, spread {r["spread"]:.0f}; '
              f'oggi N15 ordini {a["orders"]}, commissioni {a["fees"]:.0f}, spread {a["spread"]:.0f}')
