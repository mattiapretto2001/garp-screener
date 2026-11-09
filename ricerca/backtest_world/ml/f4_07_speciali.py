# f4_07: famiglia C, situazioni speciali.
# C1 quotate da 1-3 anni (age_y da IPODate EODHD; quasi solo USA); variante quotate da meno di 1 anno.
# C2 fine del lock-up (USA): (a) rendimento in eccesso su SPY nelle sedute [-10,+10] attorno a IPO+180 giorni;
#    (b) target delle righe trimestrali con eta' 0,5-0,75 anni (la prima data dopo la scadenza del lock-up).
# C3 spin-off: elenco USA stockanalysis.com 2010-2025 + elenco manuale non USA (grandi casi); righe da 1 mese a 2 anni dopo.
import os, numpy as np, pandas as pd
from f4_common import load, evaluate, fmt, OUT, HERE
BT = os.path.dirname(HERE)
F = load()
R = []
ha = F.age_y.notna()
for reg in ['tutte', 'USA', 'Europa']:
    rm = ha if reg == 'tutte' else ha & (F.reg == reg)
    R.append(evaluate(F, F.age_y.between(1, 3, inclusive='left'), rm, f'C1 quotate da 1-3 anni [{reg}]'))
    R.append(evaluate(F, F.age_y < 1, rm, f'C1b quotate da <1 anno [{reg}]'))
for lst in ['GARP', 'core']:
    R.append(evaluate(F, F.age_y.between(1, 3, inclusive='left'), ha & F[lst], f'C1 quotate da 1-3 anni dentro {lst}'))
R.append(evaluate(F, F.age_y.between(0.5, 0.75, inclusive='left'), ha & (F.reg == 'USA'), 'C2b prima data dopo il lock-up [USA]'))
# ---- C2a evento lock-up
P = pd.read_pickle(f'{BT}/eod/US.pkl'); spy = pd.read_pickle(f'{BT}/eod/bench.pkl')['SPY.US'].a
FD = pd.read_pickle(f'{BT}/fund/fund2.pkl')   # IPODate di EODHD
ipo = pd.Series({t: pd.to_datetime((FD.get(t, {}).get('gen') or {}).get('IPODate'), errors='coerce') for t in F[F.ex == 'US'].t.unique()}).dropna()
ipo = ipo[ipo >= '2011-01-01']
ev = []
for t, d0 in ipo.items():
    c = t[:-3]
    if c not in P: continue
    a = P[c].a.astype(float).dropna(); a = a[a > 0]
    if len(a) < 60 or a.index[0] > d0 + pd.Timedelta(days=30): continue
    e = a.index.searchsorted(d0 + pd.Timedelta(days=180))
    if e - 10 < 0 or e + 10 >= len(a): continue
    i0, i1 = a.index[e - 10], a.index[e + 10]
    s0, s1 = spy.asof(i0), spy.asof(i1)
    ev.append((t, d0, a.index[e], a.iloc[e + 10] / a.iloc[e - 10] - s1 / s0, a.iloc[e] / a.iloc[e - 10] - spy.asof(a.index[e]) / s0))
E = pd.DataFrame(ev, columns=['t', 'ipo', 'evento', 'car_m10_p10', 'car_m10_0'])
E['anno'] = E.evento.dt.year
y = E.groupby('anno').car_m10_p10.mean()
txt = [f'C2a eventi lock-up: {len(E)} IPO USA (universo >=300M$ almeno una volta), 2011-2026',
       f'eccesso medio [-10,+10]: {E.car_m10_p10.mean()*100:+.2f}% (mediana {E.car_m10_p10.median()*100:+.2f}%), [-10,0]: {E.car_m10_0.mean()*100:+.2f}%',
       f't fra anni (media annuale, {len(y)} anni): {y.mean()/(y.std(ddof=1)/np.sqrt(len(y))):.2f}; quota negativi {(E.car_m10_p10<0).mean()*100:.0f}%',
       'per anno: ' + ', '.join(f'{k}:{v*100:+.1f}' for k, v in y.items())]
open(f'{OUT}/f4_07_lockup.txt', 'w').write('\n'.join(txt)); print('\n'.join(txt))
# ---- C3 spin-off
U = pd.read_csv(f'{OUT}/spin_usa_stockanalysis.csv'); U['t'] = U.new.str.replace('.', '-', regex=False) + '.US'
N = pd.read_csv(f'{OUT}/spin_nonusa_manuale.csv'); N['t'] = N.new
Sp = pd.concat([U[['date', 't']].assign(src='USA'), N[['date', 't']].assign(src='non USA')]); Sp['date'] = pd.to_datetime(Sp.date)
alias = {}
for t in Sp.t:      # ticker attuali di societa' fallite (suffisso Q): provo anche senza
    if t not in set(F.t) and t.endswith('Q.US'): alias[t] = t.replace('QQ.US', '.US').replace('Q.US', '.US')
Sp['t2'] = Sp.t.map(lambda x: alias.get(x, x))
first = F.groupby('t').date.min()
ok, miss = [], []
for _, r in Sp.iterrows():
    if r.t2 in first.index and first[r.t2] >= r.date - pd.Timedelta(days=120): ok.append(r)
    elif r.t2 in first.index: miss.append((r.t2, 'nel pannello prima dello scorporo (ticker riusato?)'))
    else: miss.append((r.t2, 'non nell universo (<300M$, illiquida o borsa non coperta)'))
Sp = pd.DataFrame(ok)
print('spin-off nell universo:', len(Sp), 'di cui USA', (Sp.src == 'USA').sum(), '; esclusi', len(miss))
sig = pd.Series(False, index=F.index)
for _, r in Sp.iterrows():
    m = (F.t == r.t2) & (F.date >= r.date + pd.Timedelta(days=30)) & (F.date <= r.date + pd.Timedelta(days=730))
    sig |= m
R.append(evaluate(F, sig, F.t.notna(), 'C3 spin-off 0-2 anni [tutte]'))
R.append(evaluate(F, sig, F.reg == 'USA', 'C3 spin-off 0-2 anni [USA]'))
R.append(evaluate(F, sig, F.reg != 'USA', 'C3 spin-off 0-2 anni [non USA]'))
for lst in ['GARP', 'core']:
    R.append(evaluate(F, sig, F[lst], f'C3 spin-off dentro {lst}'))
Sp.to_csv(f'{OUT}/spin_usate.csv', index=False)
D = pd.concat(R, ignore_index=True); fmt(D).to_csv(f'{OUT}/f4_07_speciali.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
print(fmt(D).to_string())
