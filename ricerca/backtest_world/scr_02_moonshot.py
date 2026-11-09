# scr_02: Moonshot sui dati mondiali; sovrapposizione con Radar A e core; lista "crescita" unica divisa per taglia.
import pandas as pd, numpy as np
from scr_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
ROWS = []
SZ = mc.between(3e8, 15e9)
for reg, R in REG.items():
    U = UNI & R
    for nm, m in [('Moonshot (docstring, 70% del massimo)', M), ('Moonshot (codice attuale, solo media 200 gg)', M_LIVE)]:
        o, r = ev(nm, m, U, reg); ROWS += o
        o2, _ = ev(nm + ' vs universo 0,3-15 Mld$', m, U & SZ, reg, r=r); ROWS += o2
    print(reg, flush=True)
# crescita unica per taglia
for sz in ['piccole 0,3-2', 'medie 2-15', 'grandi >15']:
    S = SIZE3 == sz
    for reg in ['Mondo', 'USA grandi', 'USA piccole/medie', 'Europa', 'Asia']:
        o, _ = ev('Crescita ' + sz, CR, UNI & REG[reg] & S, reg); ROWS += o
o, _ = ev('Radar A (>=2 Mld$)', RADA, UNI & (mc >= 2e9), 'Mondo'); ROWS += o
o, _ = ev('Crescita >=2 Mld$ (medie+grandi)', CR, UNI & (mc >= 2e9), 'Mondo'); ROWS += o
o, _ = ev('Radar A oppure Crescita, >=2 Mld$', (RADA | CR), UNI & (mc >= 2e9), 'Mondo'); ROWS += o
o, _ = ev('Core (>=2 Mld$, guardia PEG)', CORE, UNI, 'Mondo'); ROWS += o
T = pd.DataFrame(ROWS); T.to_csv(f'{BASE}/res/scr_02_moonshot.csv', index=False)
print(fmt(T).to_string())
print(T[T.periodo == '2012-26'][['gruppo', 'variante', 'n', 'maxdd', 'W5', 'L20']].round(3).to_string())
# sovrapposizioni (media per data)
def ov(a, b):
    x = F[a].groupby('date').t.apply(set); y = F[b].groupby('date').t.apply(set)
    s = [len(x[d] & y.get(d, set())) / len(x[d]) for d in x.index if len(x[d])]
    return np.mean(s), F[a].groupby('date').size().mean()
for an, a in [('Moonshot', M), ('Radar A', RADA), ('Core', CORE), ('Crescita', CR)]:
    for bn, b in [('Moonshot', M), ('Radar A', RADA), ('Core', CORE), ('GARP lista', A), ('Crescita', CR)]:
        if an != bn: print(f'{an} che sono anche in {bn}: {ov(a, b)[0]:.2f}  (titoli medi {an} {ov(a, b)[1]:.1f})')
print('Moonshot per taglia', F[M].groupby(SIZE3[M]).size() / M.sum())
print('Moonshot per regione', F[M].reg.value_counts(normalize=True).round(2).to_dict())
# a caso
C = []
for nm, m, pool in [('Moonshot', M, UNI & SZ), ('Crescita piccole', CR & (SIZE3 == 'piccole 0,3-2'), UNI & (SIZE3 == 'piccole 0,3-2')),
                    ('Crescita medie', CR & (SIZE3 == 'medie 2-15'), UNI & (SIZE3 == 'medie 2-15')),
                    ('Crescita grandi', CR & (SIZE3 == 'grandi >15'), UNI & (SIZE3 == 'grandi >15'))]:
    C.append(dict(variante=nm, **caso(m, pool))); print(C[-1], flush=True)
pd.DataFrame(C).to_csv(f'{BASE}/res/scr_02_caso.csv', index=False)
# oggi
d = REB[-1]
print('Moonshot all\'ultima data', F[M & (F.date == d)][['t', 'name', 'mcap_usd', 'revq', 'gm']].sort_values('revq').to_string())
