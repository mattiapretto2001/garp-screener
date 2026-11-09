import sys, os, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
from world_04_features import clean
pool,src=P9.series_pool()
U=pd.read_pickle(f'{ML}/storico5/universo_prezzi_us_v2.pkl')
for t,day in [('MAY','2005-09-29'),('SGP_old1','2008-01-08'),('KRB','2005-07-29'),('SHU','2003-08-22'),('CKR','2008-05-15'),('BRE','2008-01-25'),('SKYF','2007-06-25'),('ASRT','2001-12-20')]:
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index(); d=d[(d.c>0)&d.a.notna()]
    aa,spx=clean(d); d=d.assign(aa=aa)
    k=d.index.searchsorted(pd.Timestamp(day))
    print('\n',t,src[t],'ultima data',d.index[-1].date(),'n',len(d)); print(d.iloc[max(0,k-3):k+4].to_string())
    print(U[(U.t==t)&U.storico][['date','px','dv63','p52','f12','f12_end','name']].tail(6).to_string())
