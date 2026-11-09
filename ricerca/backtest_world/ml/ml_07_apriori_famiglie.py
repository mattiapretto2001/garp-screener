# ml_07: perche' il punteggio a priori a pesi uguali batte i modelli stimati sul rango? Scomposizione per famiglia
# (solo descrittiva, 2016-2025, nessuna scelta di variabili fatta qui) e confronto con i segni stimati.
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
M = mc.load(); M = M[(M.date >= '2016-01-01') & M.rk12_reg.notna()]
rows = []
fams = {f: [v for v in vs if v in mc.GLOBAL and fv3.DIRECTION.get(v, 0) != 0] for f, vs in fv3.FAMILIES.items()}
fams['TUTTE (apr)'] = [v for v in mc.GLOBAL if fv3.DIRECTION.get(v, 0) != 0]
for f, vs in fams.items():
    if not vs: continue
    sc = M[mc.xcols(vs)].mean(axis=1)
    s = mc.ic_by_date(sc.values, M.rk12_reg.values, M.date.values)
    yr = s.groupby(s.index.year).mean()
    r = dict(famiglia=f, n_var=len(vs), IC=s.mean(), t=fv3.nw_t(s, 4))
    for p in mc.PERS: r[p] = s[[mc.perlab(d) == p for d in s.index]].mean()
    r.update({str(y): v for y, v in yr.items()})
    for k in ['top5_reg', 'bot20_reg']:
        a = mc.auc_by_date(sc.values, M[k].values, M.date.values); r['AUC_' + k] = a.mean()
    rows.append(r)
T = pd.DataFrame(rows); T.to_csv(f'{mc.OUT}/apriori_famiglie.csv', index=False)
pd.set_option('display.width', 250); print(T.round(3).to_string())
