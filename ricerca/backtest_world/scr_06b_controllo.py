# scr_06b: il vantaggio dei "2+ segnali" e' solo il core travestito? Controllo senza il core e contro il core.
import pandas as pd, numpy as np
from scr_common import *
nf = (CORE | TOP30).astype(int) + RADA.astype(int) + M.astype(int) + SV.astype(int) + Q3.astype(int)
nx = TOP30.astype(int) + RADA.astype(int) + M.astype(int) + SV.astype(int) + Q3.astype(int)   # senza il core
R = []
for nm, m in [('core da solo (riferimento)', CORE), ('2+ famiglie', nf >= 2), ('fuori dal core: 1 segnale', (nx == 1) & ~CORE),
              ('fuori dal core: 2+ segnali', (nx >= 2) & ~CORE)]:
    o, r = ev(nm, m, ALL, 'controllo'); R += o
    if nm.startswith('core'): rc = r
    if nm == '2+ famiglie':
        for p, (a, b) in PALL.items():
            ds = [x for x in REB if pd.Timestamp(a) <= x <= pd.Timestamp(b)]
            R.append(dict(gruppo='controllo', variante='t (2+ famiglie meno core)', periodo=p, t=tstat((r - rc)[ds])))
T = pd.DataFrame(R); T.to_csv(f'{BASE}/res/scr_06b.csv', index=False)
pd.set_option('display.width', 250)
print(fmt(T[~T.variante.str.startswith('t (')]).to_string()); print(T[T.variante.str.startswith('t (')][['periodo', 't']].round(2).to_string())
print(T[T.periodo == '2012-26'][['variante', 'maxdd', 'W5', 'L20']].round(3).to_string())
