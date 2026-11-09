# Fase 1: prezzi.  uso: python world_01_prices.py ticker EX1 EX2 ...   (prezzi giornalieri per titolo, 1 credito)
#                       python world_01_prices.py bulk EX ...            (istantanee semestrali di tutta la borsa, 100 crediti)
#                       python world_01_prices.py list FILE              (prezzi per una lista di ticker COD.EX)
import sys, pickle, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from world_common import *

mode = sys.argv[1]
if mode == 'bulk':
    dates = pd.date_range('2011-06-30', '2026-06-30', freq='6ME')
    for ex in sys.argv[2:]:
        fn = f'{BASE}/eod/bulk_{ex}.pkl'
        if os.path.exists(fn): continue
        def one(d):
            for k in range(6):  # se il giorno e' festivo si torna indietro
                dd = (d - pd.Timedelta(days=k)).strftime('%Y-%m-%d')
                j = get(f'https://eodhd.com/api/eod-bulk-last-day/{ex}?fmt=json&date={dd}')
                if j:
                    x = pd.DataFrame(j)[['code', 'close', 'volume']]; x['date'] = d; return x
            return None
        with ThreadPoolExecutor(6) as P: R = [r for r in P.map(one, dates) if r is not None]
        pd.concat(R).to_pickle(fn); print(ex, 'bulk', len(R), flush=True)
else:
    if mode == 'ticker':
        jobs = []
        for ex in sys.argv[2:]:
            s = symbols(ex); jobs.append((ex, list(s.Code)))
    else:
        L = [l.strip() for l in open(sys.argv[2]) if l.strip()]
        by = {}
        for t in L: c, e = t.rsplit('.', 1); by.setdefault(e, []).append(c)
        jobs = list(by.items())
    for ex, codes in jobs:
        fn = f'{BASE}/eod/{ex}.pkl'
        D = pickle.load(open(fn, 'rb')) if os.path.exists(fn) else {}
        todo = [c for c in codes if c not in D]
        def one(c): return c, eod_frame(get(f'https://eodhd.com/api/eod/{c}.{ex}?fmt=json&from=2010-01-01'))
        with ThreadPoolExecutor(12) as P:
            for c, d in P.map(one, todo): D[c] = d
        pickle.dump(D, open(fn, 'wb'))
        print(ex, len(todo), 'scaricati', sum(v is not None for v in D.values()), 'con dati', 'crediti', usage(), flush=True)
