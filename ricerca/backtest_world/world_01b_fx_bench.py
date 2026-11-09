# Cambi (USD per unita' di valuta) e indici di riferimento.
import pickle, pandas as pd
from world_common import *
CURS = 'EUR GBP CHF SEK DKK NOK CAD TWD KRW AUD JPY CNY HKD NZD SGD ZAR INR BRL ILS PLN RUB MXN ISK CZK HUF TRY IDR MYR PHP THB CLP ARS'.split()
FX = {}
for c in CURS:
    d = eod_frame(get(f'https://eodhd.com/api/eod/{c}USD.FOREX?fmt=json&from=2010-01-01'))
    if d is not None and len(d) > 1000: FX[c] = d.c.astype(float)
    else:
        d = eod_frame(get(f'https://eodhd.com/api/eod/USD{c}.FOREX?fmt=json&from=2010-01-01'))
        if d is not None: FX[c] = 1 / d.c.astype(float)
FX = pd.DataFrame(FX); FX = FX[(FX.index >= '2010-01-01')]
FX['USD'] = 1.0; FX['GBX'] = FX.GBP / 100; FX['GBp'] = FX.GBX; FX['ZAC'] = FX.ZAR / 100; FX['ILA'] = FX.ILS / 100
FX.to_pickle(f'{BASE}/eod/fx.pkl'); print(FX.ffill().iloc[-1])
B = {}
for t in ['VWCE.XETRA', 'IWDA.AS', 'EUNL.XETRA', 'URTH.US', 'ACWI.US', 'SPY.US', 'VT.US']:
    B[t] = eod_frame(get(f'https://eodhd.com/api/eod/{t}?fmt=json&from=2010-01-01'))
    print(t, None if B[t] is None else (B[t].index[0].date(), len(B[t])))
pickle.dump(B, open(f'{BASE}/eod/bench.pkl', 'wb'))
