# Fase 2: pre-filtro di liquidita' (prima dei fondamentali, per risparmiare crediti).
# Valore scambiato giornaliero mediano (trimestrale) in USD con cambi approssimati: serve solo a scartare le micro-cap.
import pickle, sys, pandas as pd, numpy as np
from world_common import *
FXA = {'EUR': 1.12, 'SEK': 0.1, 'DKK': 0.15, 'NOK': 0.1, 'CHF': 1.05, 'CAD': 0.76, 'TWD': 0.032, 'KRW': 0.00078, 'GBX': 0.013, 'GBP': 1.3, 'AUD': 0.72, 'USD': 1}
CUR = {'XETRA': 'EUR', 'PA': 'EUR', 'AS': 'EUR', 'MC': 'EUR', 'BR': 'EUR', 'HE': 'EUR', 'SW': 'CHF', 'ST': 'SEK', 'CO': 'DKK', 'OL': 'NOK', 'TO': 'CAD', 'TW': 'TWD', 'KO': 'KRW'}
def stats():
    rows = []
    for ex, cur in CUR.items():
        D = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
        for c, d in D.items():
            if d is None or len(d) < 60: continue
            tv = (d.c * d.v * FXA[cur]).resample('QE').median()
            px = d.c.resample('QE').last() * FXA[cur]
            ok = (tv[(px >= 1)]).dropna()
            rows.append((ex, c, (ok >= 1e6).sum(), (ok >= 3e6).sum(), (ok >= 5e6).sum(), (ok >= 3e5).sum(), (ok >= 1e7).sum()))
    for ex, fx in [('US', 1), ('LSE', 0.013), ('AU', 0.72)]:
        b = pd.read_pickle(f'{BASE}/eod/bulk_{ex}.pkl'); s = symbols(ex)
        m = dict(zip(s.Code.str.replace('_old', ''), s.Code)); m.update(dict(zip(s.Code, s.Code)))
        b = b[b.code.isin(m)].copy(); b['code'] = b.code.map(m)
        b['tv'] = b.close * b.volume * fx; b = b[b.close * fx >= 1]
        for c, g in b.groupby('code'):  # istantanee semestrali: valori x2 per confrontarli con i trimestri
            rows.append((ex, c, 2 * (g.tv >= 1e6).sum(), 2 * (g.tv >= 3e6).sum(), 2 * (g.tv >= 5e6).sum(), 2 * (g.tv >= 3e5).sum(), 2 * (g.tv >= 1e7).sum()))
    return pd.DataFrame(rows, columns=['ex', 'code', 'n1m', 'n3m', 'n5m', 'n300k', 'n10m'])
if __name__ == '__main__':
    S = stats(); S.to_pickle(f'{BASE}/res/liq.pkl')
    print(S.groupby('ex')[['n300k', 'n1m', 'n3m', 'n5m', 'n10m']].agg(lambda x: (x >= 2).sum()))
