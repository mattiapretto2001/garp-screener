# 07/11: candidati USA piccole e medie (oltre ai 1.870 grandi gia' scaricati il 06/11).
# Regola di pre-selezione (stessa usata poi per la liquidita' point-in-time): prezzo >=3$ e scambi >=3 M$ al giorno
# in almeno 3 istantanee semestrali (2011-2026). Esclusi nomi tipici di banche/REIT/SPAC/minerarie (risparmio crediti).
import pandas as pd
from world_common import *
C = pd.read_csv(f'{BASE}/res/candidates.csv'); have = set(C[C.ex == 'US'].code)
b = pd.read_pickle(f'{BASE}/eod/bulk_US.pkl'); s = symbols('US')
m = dict(zip(s.Code.str.replace('_old', ''), s.Code)); m.update(dict(zip(s.Code, s.Code)))
b = b[b.code.isin(m)].copy(); b['code'] = b.code.map(m)
pat = r'\b(?:Bank|Banc|Bancorp|Bancshares|Financial|Acquisition|Trust|REIT|Realty|Properties|Insurance|Petroleum|Mining|Gold|Fund|Capital Corp|Investment)\b'
nm = s.set_index('Code').Name
x = b[(b.close >= 3) & (b.close * b.volume >= 3e6)]; n = x.groupby('code').size(); keep = n[n >= 3].index
keep = [c for c in keep if c not in have and not pd.Series([nm.get(c, '')]).str.contains(pat, case=False, regex=True)[0]]
N = pd.DataFrame({'ex': 'US', 'code': keep}); N['t'] = N.code + '.US'
print(len(N), 'delisted', int(s.set_index('Code').delisted.reindex(keep).sum()))
N.to_csv(f'{BASE}/res/candidates_us2.csv', index=False)
open(f'{BASE}/res/eod_needed_us2.txt', 'w').write('\n'.join(N.t))
