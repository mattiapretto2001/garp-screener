# Prova A (08/11/2026), controllo dei dati: frazionamenti EODHD (1 credito a codice) per tutti i titoli dell'universo USA
# 2000-2011, v1 e v2. Servono a capire, frazionamento per frazionamento, se EODHD da' prezzo di chiusura e volume
# "grezzi" (come scambiati allora) o gia' corretti: per alcune serie di societa' uscite (es. SYNI, MATN) gli scambi in
# dollari calcolati dal pannello sono gonfiati di 20-240 volte. Tetto: si ferma se il contatore supera TETTO.
# Scrive storico5/splits_A/<codice>.json (lista, anche vuota). Riprende da dove si era fermato.
import os, sys, json, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from s5_common import OUT, get, usage
TETTO = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
D = f'{OUT}/splits_A'; os.makedirs(D, exist_ok=True)
U = pd.read_pickle(f'{OUT}/universo_prezzi_us_v2.pkl'); U0 = pd.read_pickle(f'{OUT}/universo_prezzi_us.pkl')
T = sorted(set(U[U.storico].t) | set(U0[U0.storico].t))
todo = [t for t in T if not os.path.exists(f'{D}/{t}.json')]
u0 = usage(); print('codici', len(T), '| da scaricare', len(todo), '| contatore', u0, '| tetto', TETTO, flush=True)
if u0 is None or u0 + len(todo) > TETTO: raise SystemExit('supererei il tetto')


def one(t):
    j = get(f'splits/{t}.US', **{'from': '1990-01-01'})
    if j in ('LIMIT', 'ERR'): return t, j
    json.dump(j if isinstance(j, list) else [], open(f'{D}/{t}.json', 'w'))
    return t, 'ok'


bad = []
with ThreadPoolExecutor(6) as ex:
    for k, (t, s) in enumerate(ex.map(one, todo)):
        if s != 'ok': bad.append((t, s))
        if s == 'LIMIT': break
        if k % 1000 == 0: print(k, 'fatti | errori', len(bad), time.strftime('%H:%M:%S'), flush=True)
print('errori', bad[:20], len(bad))
print('crediti', u0, '->', usage())
