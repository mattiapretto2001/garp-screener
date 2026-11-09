# Funzioni comuni: download EODHD (chiave iniettata dal proxy), liste, salvataggi compatti.
import json, urllib.request, time, os, pandas as pd, numpy as np
BASE = os.path.dirname(os.path.abspath(__file__))
HOME = {'XETRA': ['DE'], 'PA': ['FR'], 'AS': ['NL'], 'MC': ['ES'], 'BR': ['BE'], 'SW': ['CH'], 'ST': ['SE'], 'CO': ['DK'],
        'HE': ['FI'], 'OL': ['NO'], 'LSE': ['GB', 'JE', 'GG', 'IM'], 'TO': ['CA'], 'TW': ['TW'], 'KO': ['KR'], 'AU': ['AU'], 'US': None}
REGION = {**{e: 'Europa' for e in ['XETRA', 'PA', 'AS', 'MC', 'BR', 'SW', 'ST', 'CO', 'HE', 'OL', 'LSE']},
          'TO': 'Canada', 'TW': 'Asia', 'KO': 'Asia', 'AU': 'Australia', 'US': 'USA'}
US_EX = {'NYSE', 'NASDAQ', 'NYSE MKT', 'AMEX', 'NYSE ARCA', 'BATS'}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if e.code == 429: time.sleep(20)
            else: time.sleep(2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return None


def usage():
    j = get('https://eodhd.com/api/user?fmt=json'); return j.get('apiRequests') if j else None


def symbols(ex):
    out = []
    for d in (0, 1):
        for x in json.load(open(f'{BASE}/lists/{ex}_{d}.json')):
            x['delisted'] = d; out.append(x)
    df = pd.DataFrame(out).drop_duplicates('Code', keep='first')
    df['pre'] = df.Isin.fillna('').str[:2]
    if ex == 'US':
        df = df[df.Exchange.isin(US_EX)]
    else:
        df = df[df.pre.isin(HOME[ex]) | (df.pre == '')]
    df['ex'] = ex
    return df.reset_index(drop=True)


def eod_frame(j):
    if not j or not isinstance(j, list): return None
    d = pd.DataFrame(j)
    if d.empty or 'adjusted_close' not in d: return None
    d.index = pd.to_datetime(d.date)
    return d[['close', 'adjusted_close', 'volume']].astype('float32').rename(columns={'close': 'c', 'adjusted_close': 'a', 'volume': 'v'})
