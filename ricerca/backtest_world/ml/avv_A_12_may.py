import sys, os, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
pool,src=P9.series_pool()
for t in ['MAY','KRB','FBF','MVL','RX']:
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index()
    g=d.groupby(d.index.year).agg(n=('c','size'),c_med=('c','median'),v_pos=('v',lambda s:(s>0).mean()),v_med=('v','median'),cambi=('c',lambda s:(s.diff()!=0).mean()))
    print(t, src[t]); print(g.T.round(3).to_string())
