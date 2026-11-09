# scr_01b: ricalcola solo il rendimento da dividendo (correzione del segno in scr_01) e aggiorna res/scr_extra.pkl
import pickle, pandas as pd, numpy as np
from world_common import BASE
import importlib.util, sys
src = open(f'{BASE}/scr_01_extra.py').read()
ns = {}; exec(src[src.index('def divyield'):src.index('def annual_hist')], {'pd': pd, 'np': np}, ns)
X = pd.read_pickle(f'{BASE}/res/scr_extra.pkl')
P2 = pd.read_pickle(f'{BASE}/res/panel2.pkl')[['t', 'date', 'ex']]
out = []
for ex, g in P2.groupby('ex'):
    P = pickle.load(open(f'{BASE}/eod/{ex}.pkl', 'rb'))
    for t, h in g.groupby('t'):
        code = t.rsplit('.', 1)[0]
        if code not in P or P[code] is None: continue
        d = ns['divyield'](P[code], sorted(h.date))
        out += [(t, k, v) for k, v in d.items()]
    print(ex, flush=True)
D = pd.DataFrame(out, columns=['t', 'date', 'divy'])
X = X.drop(columns='divy').merge(D, on=['t', 'date'], how='left')
X.to_pickle(f'{BASE}/res/scr_extra.pkl'); print(X.divy.describe())
