# Liquidita' "point-in-time": a ogni data un titolo entra nell'universo solo se la regola di pre-selezione
# (la stessa usata per scegliere i candidati) era gia' soddisfatta con i dati fino a quella data.
# Evita il vantaggio di sapere oggi quali societa' sono diventate grandi e scambiate.
import pickle, pandas as pd, numpy as np
from world_common import *
from world_02_candidates import FXA, CUR
C = pd.read_csv(f'{BASE}/res/candidates.csv')
REB = list(pd.date_range('2011-12-31', '2026-09-30', freq='QE'))
EU = ['AS', 'BR', 'CO', 'HE', 'MC', 'OL', 'PA', 'ST', 'SW', 'XETRA']
rows = []
for ex, cur in CUR.items():
    thr = 3e6 if ex in EU or ex == 'TO' else 1e7
    D = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
    for code in C[C.ex == ex].code:
        d = D.get(code)
        if d is None: continue
        tv = (d.c * d.v * FXA[cur]).resample('QE').median(); px = d.c.resample('QE').last() * FXA[cur]
        hit = ((tv >= thr) & (px >= 1)).astype(int).cumsum()
        for t in REB:
            h = hit[hit.index <= t]
            rows.append((f'{code}.{ex}', t, (h.iloc[-1] if len(h) else 0) >= 2))
for ex, fx, thr, k, pmin in [('US', 1, 5e7, 3, 3), ('LSE', 0.013, 3e6, 1, 1), ('AU', 0.72, 3e6, 1, 1)]:
    b = pd.read_pickle(f'{BASE}/eod/bulk_{ex}.pkl'); s = symbols(ex)
    m = dict(zip(s.Code.str.replace('_old', ''), s.Code)); m.update(dict(zip(s.Code, s.Code)))
    b = b[b.code.isin(m)].copy(); b['code'] = b.code.map(m)
    b['hit'] = (b.close * b.volume * fx >= thr) & (b.close * fx >= pmin)
    snaps = sorted(b.date.unique())
    g = {c: x.set_index('date').hit for c, x in b.groupby('code')}
    for code in C[C.ex == ex].code:
        h = g.get(code)
        for t in REB:
            avail = sum(1 for d in snaps if d <= t)
            n = int(h[h.index <= t].sum()) if h is not None else 0
            rows.append((f'{code}.{ex}', t, n >= min(k, avail)))
L = pd.DataFrame(rows, columns=['t', 'date', 'liq'])
L.to_pickle(f'{BASE}/res/liq_pit.pkl')
print(L.groupby('date').liq.sum().iloc[[0, 1, 2, 4, 10, 30, -1]])
