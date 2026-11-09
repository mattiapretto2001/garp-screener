import pandas as pd, numpy as np
A = pd.read_pickle('regoleC/dati/runs.pkl'); A = A[(~A.tax) & A.key.isin(['P1', 'P2'])].assign(mod='rapporto')
B = pd.read_pickle('avv_C_out/runs_robusto.pkl')
X = pd.concat([A, B])
V = [('L', 'none'), ('L', 'TR3'), ('L', 'AD30'), ('L', 'S30'), ('T2', 'none'), ('T3', 'none')]
rows = []
for (key, mod), g in X.groupby(['key', 'mod']):
    ref = g[(g.base == 'L') & (g.over == 'none')].set_index('seed')
    r = dict(key=key, mod=mod, W=g.cagr_w.iloc[0] * 100, base_s=ref.cagr_s.median() * 100, base_cr=ref.cagr_cr.median() * 100,
             trades=ref.trades_y.median())
    for b, o in V[1:]:
        h = g[(g.base == b) & (g.over == o)].set_index('seed')
        if not len(h): continue
        r[f'{b}/{o}'] = (h.cagr_cr.median() - ref.cagr_cr.median()) * 100
    rows.append(r)
R = pd.DataFrame(rows).set_index(['key', 'mod'])
pd.set_option('display.width', 250)
print('50/50 ribilanciato: base (mediana) e differenza delle mediane di ogni regola rispetto alla base, in punti l anno')
print(R.round(2).to_string())
