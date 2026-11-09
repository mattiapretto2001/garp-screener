# 07/11: bilanci completi in forma compatta, con i campi in piu' (margine lordo, R&S, spese generali, attivo/passivo corrente,
# storico utili con stime e sorprese, data di IPO). Il JSON completo non viene salvato.
# uso: python world_11_fund2.py LISTA.txt [tetto_crediti]
import sys, pickle, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from world_common import *
import world_03_fund as W3
W3.INC = W3.INC + ['grossProfit', 'costOfRevenue', 'researchDevelopment', 'sellingGeneralAdministrative']
W3.BAL = W3.BAL + ['totalCurrentAssets', 'totalCurrentLiabilities']


def extract(j):
    out = W3.extract(j)
    eh = (j.get('Earnings') or {}).get('History')
    if isinstance(eh, dict):
        rows = [dict(date=k, reportDate=v.get('reportDate'), epsActual=v.get('epsActual'), epsEstimate=v.get('epsEstimate'),
                     surprisePercent=v.get('surprisePercent'), bam=v.get('beforeAfterMarket')) for k, v in eh.items() if isinstance(v, dict)]
        e = pd.DataFrame(rows)
        if len(e):
            e['date'] = pd.to_datetime(e.date, errors='coerce'); e['reportDate'] = pd.to_datetime(e.reportDate, errors='coerce')
            for c in ['epsActual', 'epsEstimate', 'surprisePercent']: e[c] = pd.to_numeric(e[c], errors='coerce').astype('float32')
            out['earn'] = e.dropna(subset=['date']).sort_values('date').reset_index(drop=True)
    for k in list(out):   # compatta: float32
        v = out[k]
        if isinstance(v, pd.DataFrame):
            for c in v.columns:
                if v[c].dtype == 'float64': v[c] = v[c].astype('float32')
    return out


if __name__ == '__main__':
    L = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    STOP = int(sys.argv[2]) if len(sys.argv) > 2 else 79000
    fn = f'{BASE}/fund/fund2.pkl'
    D = pickle.load(open(fn, 'rb')) if os.path.exists(fn) else {}
    todo = [t for t in L if D.get(t) is None]   # anche quelli falliti (429) in un giro precedente
    print('da scaricare', len(todo), 'crediti ora', usage(), flush=True)
    def one(t):
        j = get(f'https://eodhd.com/api/fundamentals/{t}?fmt=json')
        if not j or not isinstance(j, dict): return t, None
        try: return t, extract(j)
        except Exception as e: return t, {'err': str(e)}
    for i in range(0, len(todo), 250):
        u = usage()
        if u and u > STOP - 2600: print('STOP crediti', u, flush=True); break
        with ThreadPoolExecutor(10) as P:
            for t, d in P.map(one, todo[i:i + 250]): D[t] = d
        pickle.dump(D, open(fn, 'wb'))
        print(i + 250, 'fatti; crediti', usage(), flush=True)
    print('fine; con dati', sum(1 for v in D.values() if v and 'gen' in v), 'su', len(D), 'crediti', usage(), flush=True)
