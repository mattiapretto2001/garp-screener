import sys, os, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
from world_04_features import clean
pool,src=P9.series_pool()
for t,day in [('EA','2003-11-18'),('EA','2000-09-11'),('KSU','2000-07-13'),('REV','2008-09-15'),('JDSU','2006-11-14'),('SLP','2007-10-02'),('JCI','2007-07-02'),('NXGN','2006-03-27')]:
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index(); d=d[(d.c>0)&d.a.notna()]
    aa,spx=clean(d); d=d.assign(aa=aa,spx=spx)
    k=d.index.searchsorted(pd.Timestamp(day))
    print(t,src[t]); print(d.iloc[k-3:k+3].to_string())
