# "Lista ferma": pesi uguali, rifatta a ogni nuova lista, senza costi. Calcolo mio dalle matrici di prezzo di c01.
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, 'regoleC'); import c02_sim as S
for key in ['P1', 'P2']:
    D = S.load(key); cal = D['cal']; M = D['M']; P = pickle.load(open(f'regoleC/dati/{key}.pkl', 'rb'))
    qd = sorted(P['L']); st = [int(np.searchsorted(cal.values, np.datetime64(q), side='right')) for q in qd]
    st = [s for s in st if s < len(cal)]
    v = 1.0
    for i, a in enumerate(st):
        b = st[i + 1] if i + 1 < len(st) else len(cal) - 1
        js = [j for j in P['L'][qd[i]] if not np.isnan(M[j, a])]
        if not js: continue
        r = []
        for j in js:
            if D['ended'][j] and D['last'][j] < b:
                e = D['last'][j]; r.append(0.0 if D['bk'][j] else M[j, e] / M[j, a])
            else: r.append(M[j, b] / M[j, a])
        v *= np.mean(r)
    y = (cal[-1] - cal[st[0]]).days / 365.25
    print(key, 'lista ferma, pesi uguali, senza costi: CAGR', round(v ** (1 / y) - 1, 4), 'dal', cal[st[0]].date())
