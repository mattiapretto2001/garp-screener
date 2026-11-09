# Uscite dal listino e "a zero" per anno di acquisto; titoli delle liste vere per anno con serie finita prima di oggi
import pickle, numpy as np, pandas as pd
ML = '${RICERCA_BASE}/backtest_world/ml'
POS = pickle.load(open(f'{ML}/regoleC/dati/posizioni.pkl', 'rb'))
for key in ['P1', 'P2']:
    D = pickle.load(open(f'{ML}/regoleC/dati/{key}.pkl', 'rb')); cal = D['cal']
    for rule in [('L', 'none'), ('T3', 'none')]:
        P = POS[(key,) + rule + (False,)].view(np.recarray)
        y = cal[P.d0].year
        df = pd.DataFrame(dict(y=y, zero=P.mult <= 0.1, fall=P.why == 'fallimento', usc=P.why == 'uscita dal listino', mult=P.mult))
        g = df.groupby('y').agg(n=('zero', 'size'), zero=('zero', 'mean'), fall=('fall', 'mean'), usc=('usc', 'mean'), med=('mult', 'median'))
        print(key, rule); print(g.round(3).T.to_string())
    # liste: quota di nomi con serie finita (uscita) per anno della lista
    info = D['info']; tick = D['tick']
    rows = []
    for q, arr in sorted(D['L'].items()):
        if len(arr) == 0: continue
        en = np.mean([info[tick[j]][1] and not tick[j] in () for j in arr])
        rows.append((q.year, en, len(arr)))
    R = pd.DataFrame(rows, columns=['anno', 'quota_finita', 'n']).groupby('anno').mean()
    print(key, 'quota dei nomi in lista la cui serie e finita prima di oggi (media per anno)'); print(R.round(3).T.to_string())
