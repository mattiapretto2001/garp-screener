# Storico 2000-2011, fase 1: prezzi giornalieri dal 1998 per tutti i ticker gia' noti (panel2 + fund2 [+ fund]).
# 1 credito per ticker. Salvataggio compatto: un pickle gzip per borsa, formato lungo (t, date, c, a, v).
# uso: python h01_eod_lungo.py [max_crediti]
import sys, os, json, time, pickle, urllib.request, urllib.error, pandas as pd, numpy as np
from concurrent.futures import ThreadPoolExecutor
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML)
OUT = f'{ML}/eod_lungo'; os.makedirs(OUT, exist_ok=True)
MAXC = int(sys.argv[1]) if len(sys.argv) > 1 else 11000

def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(20 if e.code == 429 else 2 + 3 * i)
        except Exception:
            time.sleep(2 + 3 * i)
    return 'ERR'

def usage():
    j = get('https://eodhd.com/api/user?fmt=json'); return j.get('apiRequests') if isinstance(j, dict) else None

p = pd.read_pickle(f'{BW}/res/panel2.pkl')
T = set(p.t.unique()); del p
T |= set(pickle.load(open(f'{BW}/fund/fund2.pkl', 'rb')).keys())
prio2 = set(pickle.load(open(f'{BW}/fund/fund.pkl', 'rb')).keys()) - T   # extra: solo se avanza budget
ORDER = ['US', 'LSE', 'XETRA', 'PA', 'ST', 'SW', 'MC', 'AS', 'CO', 'OL', 'HE', 'BR', 'TO', 'AU', 'TW', 'KO']
jobs = []
for group in (T, prio2):
    by = {}
    for t in group:
        c, e = t.rsplit('.', 1); by.setdefault(e, []).append(c)
    for e in ORDER:
        if e in by: jobs.append((e, sorted(by[e])))

u0 = usage(); print('crediti iniziali', u0, 'ticker', len(T), '+extra', len(prio2), flush=True)
json.dump({'u0': u0}, open(f'{OUT}/_u0.json', 'w'))
used = 0
for k, (ex, codes) in enumerate(jobs):
    stfn = f'{OUT}/_stato_{ex}.json'
    st = json.load(open(stfn)) if os.path.exists(stfn) else {}
    todo = [c for c in codes if c not in st]
    if not todo: continue
    if used + len(todo) > MAXC:
        todo = todo[:max(0, MAXC - used)]
        if not todo: print('budget esaurito prima di', ex, flush=True); break
    def one(c):
        j = get(f'https://eodhd.com/api/eod/{c}.{ex}?fmt=json&from=1998-01-01')
        if j == 'ERR': return c, 'ERR', None
        if not j or not isinstance(j, list): return c, 'vuoto', None
        d = pd.DataFrame(j)
        if d.empty or 'adjusted_close' not in d: return c, 'vuoto', None
        d = pd.DataFrame({'t': c, 'date': pd.to_datetime(d.date), 'c': d.close.astype('float32'),
                          'a': d.adjusted_close.astype('float32'), 'v': d.volume.astype('float32')})
        return c, 'ok', d
    for i0 in range(0, len(todo), 600):
        part = todo[i0:i0 + 600]
        R = []
        with ThreadPoolExecutor(12) as P:
            for c, s_, d in P.map(one, part):
                if s_ != 'ERR': st[c] = s_
                if d is not None: R.append(d)
        used += len(part)
        if R:
            new = pd.concat(R, ignore_index=True); new['t'] = new.t.astype('category')
            n = len([f for f in os.listdir(OUT) if f.startswith(f'part_{ex}_')])
            new.to_pickle(f'{OUT}/part_{ex}_{n:03d}.pkl')
        json.dump(st, open(stfn, 'w'))
        print(ex, 'blocco', i0, 'scaricati', len(part), 'ok tot', sum(v == 'ok' for v in st.values()), 'usati', used,
              'contatore', usage(), time.strftime('%H:%M:%S'), flush=True)
print('fine; crediti usati da questo script ~', (usage() or 0) - (u0 or 0), flush=True)
