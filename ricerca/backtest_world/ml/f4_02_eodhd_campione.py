# f4_02: campione casuale (seme 42) di 285 societa' USA dell'universo (presenti in almeno una data 2018-2025).
# Per ognuna 1 chiamata EODHD fundamentals (10 crediti) con Earnings::Trend (n. analisti per trimestre, storico dal 2017),
# General::Officers (titoli di OGGI: fondatore?) e SharesStats (quota insider di OGGI). Tetto: 2.900 crediti.
import os, json, time, urllib.request, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = f'{HERE}/f4_out/eodhd_campione'; os.makedirs(OUT, exist_ok=True)
F = pd.read_pickle(f'{HERE}/features_v3.pkl')[['t', 'date', 'ex']]
U = sorted(F[(F.ex == 'US') & (F.date >= '2018-01-01') & (F.date <= '2025-12-31')].t.unique())
S = list(np.random.default_rng(42).choice(U, 285, replace=False))
pd.Series(S).to_csv(f'{OUT}/_campione.csv', index=False)
for i, t in enumerate(S):
    p = f'{OUT}/{t}.json'
    if os.path.exists(p): continue
    url = f'https://eodhd.com/api/fundamentals/{t}?fmt=json&filter=Earnings::Trend,General::Officers,SharesStats'
    for k in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r: j = json.load(r); break
        except Exception as e:
            j = {'err': str(e)}; time.sleep(3)
    json.dump(j, open(p, 'w'))
    if i % 25 == 0: print(i, t, flush=True)
