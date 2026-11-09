import sys, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'; O=f'{ML}/storico5'
sys.path.insert(0, ML)
from sA_common import build
P=pd.read_pickle(f'{O}/pannello_prezzi_us_v2.pkl'); P=P[P.date<='2011-09-30'].reset_index(drop=True)
C=pd.read_pickle(f'{O}/volumi_corretti_A.pkl').set_index(['t','date'])
j=C.reindex(pd.MultiIndex.from_frame(P[['t','date']]))
Pv=P.copy(); hv=j.dv63_v.notna().values; Pv.loc[hv,'dv63']=j.dv63_v.values[hv]; Pv.loc[hv,'px']=j.px_v.values[hv]
U2=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H2=U2[U2.storico]; Hv=build(Pv); Hv=Hv[Hv.storico]
kk=lambda X: set(zip(X.date, X.f12.round(3), X.p52.round(2)))
a=kk(H2); b=kk(Hv)
out=H2[[x not in b for x in zip(H2.date,H2.f12.round(3),H2.p52.round(2))]]
inn=Hv[[x not in a for x in zip(Hv.date,Hv.f12.round(3),Hv.p52.round(2))]]
print('stima: escono',len(out),f'({len(out)/len(H2):.1%})','crolli',round(out.L50.mean(),3),'| entrano',len(inn),f'({len(inn)/len(H2):.1%})','crolli',round(inn.L50.mean(),3))
