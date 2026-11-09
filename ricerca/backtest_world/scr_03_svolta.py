# scr_03: Svolta B1 sui dati mondiali (regole del codice attuale, nessun ritocco).
import pandas as pd, numpy as np
from scr_common import *
pd.set_option('display.width', 250)
ROWS = []
SZ = mc.between(1e9, 15e9)
for reg, R in REG.items():
    o, r = ev('Svolta B1', SV, UNI & R, reg); ROWS += o
    o, _ = ev('Svolta B1 vs universo 1-15 Mld$', SV, UNI & R & SZ, reg, r=r); ROWS += o
T = pd.DataFrame(ROWS); T.to_csv(f'{BASE}/res/scr_03_svolta.csv', index=False)
print(fmt(T).to_string())
print(T[T.periodo == '2012-26'][['gruppo', 'variante', 'n', 'maxdd', 'W5', 'L20']].round(3).to_string())
c = caso(SV, UNI & SZ); print('caso (dentro universo 1-15 Mld$)', c)
pd.DataFrame([c]).to_csv(f'{BASE}/res/scr_03_caso.csv', index=False)
# anno per anno
r, n = run(F, SV); u = useries(UNI & SZ)
yr = lambda s: (1 + s).groupby(pd.Index([d.year for d in s.index])).prod() - 1   # anno = anno della data di acquisto (trimestre successivo)
print(pd.DataFrame({'svolta': yr(r), 'univ 1-15': yr(u), 'n medio': n.groupby(pd.Index([d.year for d in n.index])).mean()}).round(3).to_string())
print('regioni', F[SV].reg.value_counts(normalize=True).round(2).to_dict(), 'settori', F[SV].sector.value_counts(normalize=True).head(4).round(2).to_dict())
print('copertura margine lordo nell universo 1-15:', F[UNI & SZ].groupby('reg').gm.apply(lambda s: s.notna().mean()).round(2).to_dict())
print(F[SV & (F.date >= '2025-01-01')][['date', 't', 'name', 'revq', 'gm', 'opm', 'd_opm', 'f12']].sort_values('date').tail(30).to_string())
