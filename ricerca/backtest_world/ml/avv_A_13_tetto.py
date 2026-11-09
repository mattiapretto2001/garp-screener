import sys, pandas as pd, numpy as np
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, ML)
from sA_common import prep
P=pd.read_pickle(f'{ML}/storico5/pannello_prezzi_us_v2.pkl'); P=P[P.date<='2011-09-30'].reset_index(drop=True)
D,base,Q=prep(P)
B=base&D.storico&(D.cap.isna()|(D.cap>=300e6))
for c in Q:
    only=B&Q[c]
    X=D[only]
    print(c,'righe',len(X),'titoli',X.t.nunique(),'crolli f12<=-50%',round((X.f12<=-0.5).mean(),3),'f12 mediana',round(X.f12.median(),3),'p52<0.4',round((X.p52<0.4).mean(),3))
X=D[B&Q.q1_tetto]; print(X.groupby('t').agg(n=('date','size'),nome=('name','first'),f12=('f12','median'),px=('px','median')).sort_values('n',ascending=False).head(15).to_string())
