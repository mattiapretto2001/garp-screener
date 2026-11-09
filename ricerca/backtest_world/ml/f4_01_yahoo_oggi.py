# f4_01: dati di OGGI da Yahoo (nessuno storico): titoli dei dirigenti (fondatore?), quota insider, n. analisti.
# Solo per societa' presenti nell'universo in almeno una data >= 30/09/2023. Uso: python f4_01_yahoo_oggi.py
import os, json, time, pandas as pd, yfinance as yf
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f'{HERE}/f4_out/yahoo_oggi.jsonl'
SUF = {'US': '', 'XETRA': '.DE', 'LSE': '.L', 'PA': '.PA', 'AS': '.AS', 'MC': '.MC', 'BR': '.BR', 'SW': '.SW', 'ST': '.ST', 'CO': '.CO',
       'HE': '.HE', 'OL': '.OL', 'TO': '.TO', 'AU': '.AX', 'TW': '.TW', 'KO': '.KS'}
F = pd.read_pickle(f'{HERE}/features_v3.pkl', )[['t', 'date', 'ex']]
T = sorted(F[F.date >= '2023-09-30'].t.unique())
done = set()
if os.path.exists(OUT):
    for l in open(OUT): done.add(json.loads(l)['t'])
T = [t for t in T if t not in done]
print(len(T), 'da scaricare', flush=True)

def one(t):
    code, ex = t.rsplit('.', 1)
    y = code.replace('-', '.') if ex != 'US' else code.replace('.', '-')
    if ex == 'US': y = code.replace('.', '-')
    if ex in ('ST', 'CO', 'HE', 'OL'): y = code.replace('_', '-')
    y = y + SUF[ex]
    for k in range(3):
        try:
            i = yf.Ticker(y).info
            return {'t': t, 'y': y, 'ins': i.get('heldPercentInsiders'), 'nan': i.get('numberOfAnalystOpinions'),
                    'off': [(o.get('name'), o.get('title'), o.get('yearBorn')) for o in (i.get('companyOfficers') or [])][:12],
                    'name': i.get('longName')}
        except Exception as e:
            time.sleep(3 + 5 * k)
    return {'t': t, 'y': y, 'err': 1}

with open(OUT, 'a') as f, ThreadPoolExecutor(6) as ex:
    for n, r in enumerate(ex.map(one, T)):
        f.write(json.dumps(r) + '\n')
        if n % 250 == 0: print(n, flush=True); f.flush()
