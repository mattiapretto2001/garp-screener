# 07/11: liquidita' point-in-time con l'universo USA allargato. Resto del mondo come world_04b.
# USA (grandi e piccole/medie, stessa regola della pre-selezione world_10): prezzo >=3$ e scambi >=3 M$ al giorno
# in almeno 3 istantanee semestrali gia' osservate alla data (min(3, istantanee disponibili) all'inizio).
import pandas as pd
from world_common import *
L = pd.read_pickle(f'{BASE}/res/liq_pit.pkl')
L = L[~L.t.str.endswith('.US')]
C = pd.concat([pd.read_csv(f'{BASE}/res/candidates.csv'), pd.read_csv(f'{BASE}/res/candidates_us2.csv')]).drop_duplicates('t')
REB = list(pd.date_range('2011-12-31', '2026-09-30', freq='QE'))
b = pd.read_pickle(f'{BASE}/eod/bulk_US.pkl'); s = symbols('US')
m = dict(zip(s.Code.str.replace('_old', ''), s.Code)); m.update(dict(zip(s.Code, s.Code)))
b = b[b.code.isin(m)].copy(); b['code'] = b.code.map(m)
b['hit'] = (b.close * b.volume >= 3e6) & (b.close >= 3)
snaps = sorted(b.date.unique())
g = {c: x.set_index('date').hit for c, x in b.groupby('code')}
rows = []
for code in C[C.ex == 'US'].code:
    h = g.get(code)
    for t in REB:
        avail = sum(1 for d in snaps if d <= t)
        n = int(h[h.index <= t].sum()) if h is not None else 0
        rows.append((f'{code}.US', t, n >= min(3, avail)))
L = pd.concat([L, pd.DataFrame(rows, columns=['t', 'date', 'liq'])])
L.to_pickle(f'{BASE}/res/liq_pit2.pkl')
print(L[L.t.str.endswith('.US')].groupby('date').liq.sum().iloc[[0, 4, 10, 30, -1]])
