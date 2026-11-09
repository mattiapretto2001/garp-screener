# Storico 2000-2011, fase 2: quanto pesa la distorsione da sopravvivenza prima del 2011.
# (a) elenco dei delisted EODHD che non compaiono nelle istantanee 2011+ (= usciti prima di meta' 2011);
# (b) campione casuale di 200 di questi (prezzi dal 1998, 1 credito l'uno) + 15 nomi europei famosi usciti prima del 2011;
# (c) istantanee di borsa a date 2000-2010 (100 crediti l'una) per contare quanti titoli EODHD vede in quegli anni.
import sys, os, json, time, pickle, urllib.request, urllib.error, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML)
sys.path.insert(0, BW)
from world_common import symbols
OUT = f'{ML}/sopravv'; os.makedirs(OUT, exist_ok=True)

def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(20 if e.code == 429 else 2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return 'ERR'
def usage():
    j = get('https://eodhd.com/api/user?fmt=json'); return j.get('apiRequests') if isinstance(j, dict) else None

step = sys.argv[1]
if step == 'elenco':
    R = []
    for ex in ['US', 'LSE', 'AU']:
        s = symbols(ex); b = pd.read_pickle(f'{BW}/eod/bulk_{ex}.pkl'); codes = set(b.code)
        dl = s[s.delisted == 1].copy()
        dl['old'] = dl.Code.str.contains('_old')
        dl['pre2011'] = dl.old | ~dl.Code.isin(codes)
        R.append(dl)
    R = pd.concat(R, ignore_index=True); R.to_pickle(f'{OUT}/delisted_pre2011_candidati.pkl')
    print(R.groupby(['ex', 'pre2011']).size())
elif step == 'campione':
    R = pd.read_pickle(f'{OUT}/delisted_pre2011_candidati.pkl'); R = R[R.pre2011]
    rng = np.random.default_rng(2011)
    us = R[R.ex == 'US']; S = us.iloc[rng.choice(len(us), 160, replace=False)]
    for ex, n in [('LSE', 25), ('AU', 15)]:
        x = R[R.ex == ex]; S = pd.concat([S, x.iloc[rng.choice(len(x), n, replace=False)]])
    jobs = [(r.Code, r.ex) for r in S.itertuples()]
    # nomi europei/UK famosi usciti prima del 2011 (verifica: EODHD li ha?)
    fam = [('HOE', 'XETRA'), ('SCH', 'XETRA'), ('MMN', 'XETRA'), ('ALT', 'XETRA'), ('HVM', 'XETRA'), ('AVE', 'PA'), ('LOR', 'PA'),
           ('PEC', 'PA'), ('AGF', 'PA'), ('CBRY', 'LSE'), ('GLH', 'LSE'), ('BAA', 'LSE'), ('SPW', 'LSE'), ('RTR', 'LSE'), ('ABN', 'AS')]
    jobs += fam
    u0 = usage()
    def one(j):
        c, ex = j; x = get(f'https://eodhd.com/api/eod/{c}.{ex}?fmt=json&from=1998-01-01')
        if x == 'ERR' or not x or not isinstance(x, list): return c, ex, None
        d = pd.DataFrame(x); d['date'] = pd.to_datetime(d.date)
        return c, ex, d[['date', 'close', 'adjusted_close', 'volume']]
    with ThreadPoolExecutor(10) as P: res = list(P.map(one, jobs))
    pickle.dump({'jobs': jobs, 'res': res, 'campione': S}, open(f'{OUT}/campione_prezzi.pkl', 'wb'))
    print('crediti', u0, '->', usage(), 'con dati', sum(r[2] is not None for r in res), 'su', len(res))
elif step == 'bulk':
    # uso: bulk EX:YYYY-MM-DD ...
    u0 = usage()
    for spec in sys.argv[2:]:
        ex, d = spec.split(':'); fn = f'{OUT}/bulk_{ex}_{d}.pkl'
        if os.path.exists(fn): continue
        x = None
        for k in range(5):
            dd = (pd.Timestamp(d) - pd.Timedelta(days=k)).strftime('%Y-%m-%d')
            x = get(f'https://eodhd.com/api/eod-bulk-last-day/{ex}?fmt=json&date={dd}')
            if x and x != 'ERR': break
        if x and x != 'ERR':
            df = pd.DataFrame(x); df.to_pickle(fn); print(ex, d, dd, 'righe', len(df), flush=True)
        else:
            print(ex, d, 'niente', flush=True)
    print('crediti', u0, '->', usage())
elif step == 'fond':
    # uso: fond FILE_LISTA  (fondamentali completi, 10 crediti l'uno, per verificare la copertura dei delisted pre-2011)
    L = [l.strip() for l in open(sys.argv[2]) if l.strip()]
    u0 = usage()
    def one(t): return t, get(f'https://eodhd.com/api/fundamentals/{t}?fmt=json')
    with ThreadPoolExecutor(6) as P: res = dict(P.map(one, L))
    pickle.dump(res, open(f'{OUT}/fond_campione.pkl', 'wb'))
    print('crediti', u0, '->', usage(), 'con dati', sum(isinstance(v, dict) and len(v) > 0 for v in res.values()), 'su', len(L))
