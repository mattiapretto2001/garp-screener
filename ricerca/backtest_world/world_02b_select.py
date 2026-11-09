# Scelta dei candidati per i fondamentali (budget crediti): soglie di liquidita' per regione.
import pandas as pd
from world_common import *
S = pd.read_pickle(f'{BASE}/res/liq.pkl')
EU = ['AS', 'BR', 'CO', 'HE', 'MC', 'OL', 'PA', 'ST', 'SW', 'XETRA']
pat = r'\b(?:Bank|Banc|Bancorp|Bancshares|Financial|Acquisition|Trust|REIT|Realty|Properties|Insurance|Petroleum|Mining|Gold|Fund|Capital Corp|Investment)\b'
sel = []
for ex, g in S.groupby('ex'):
    if ex in EU or ex in ('LSE', 'TO', 'AU'): k = g[g.n3m >= 2]
    elif ex in ('TW', 'KO'): k = g[g.n10m >= 2]
    else:  # USA: solo i titoli molto scambiati (>=50 M$ al giorno in almeno 3 istantanee semestrali)
        b = pd.read_pickle(f'{BASE}/eod/bulk_US.pkl'); s = symbols('US')
        m = dict(zip(s.Code.str.replace('_old', ''), s.Code)); m.update(dict(zip(s.Code, s.Code)))
        b = b[b.code.isin(m)].copy(); b['code'] = b.code.map(m); b = b[(b.close >= 3) & (b.close * b.volume >= 5e7)]
        n = b.groupby('code').size(); keep = n[n >= 3].index
        nm = s.set_index('Code').Name.reindex(keep).fillna('')
        k = pd.DataFrame({'ex': 'US', 'code': [c for c in keep if not pd.Series([nm[c]]).str.contains(pat, case=False, regex=True)[0]]})
    sel.append(k[['ex', 'code']])
C = pd.concat(sel); C['t'] = C.code + '.' + C.ex
print(C.groupby('ex').size(), len(C))
C.to_csv(f'{BASE}/res/candidates.csv', index=False)
open(f'{BASE}/res/eod_needed.txt', 'w').write('\n'.join(C[C.ex.isin(['US', 'LSE', 'AU'])].t))
