# Regola -100%: quante righe contate "fallimento" avevano gia' comprato vicino al prezzo di uscita (es. Bear Stearns a 10,49 $)
import sys, os, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
from world_04_features import clean
O=f'{ML}/storico5'; A='${RICERCA_BASE}/avvA'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H=U[U.storico].copy()
X=H[(H.f12<=-0.999)&H.f12_end]
pool,src=P9.series_pool()
alt={}
for t,g in X.groupby('t'):
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index(); d=d[(d.c>0)&d.a.notna()]
    aa,_=clean(d)
    for dt in g.date:
        i=d.index.searchsorted(dt,side='right')-1; alt[(t,dt)]=aa.values[-1]/aa.values[i]-1
X=X.assign(f12_ultimo=[alt[(t,d)] for t,d in zip(X.t,X.date)])
print('righe -100% con uscita:',len(X),'| ultimo prezzo / prezzo alla data > 0,5 (non sarebbe un crollo):',(X.f12_ultimo>-0.5).sum())
print(X.assign(b=pd.cut(X.p52,[0,.4,.6,.75,.9,1.01],right=False)).groupby('b',observed=True).agg(n=('t','size'),non_crollo=('f12_ultimo',lambda s:(s>-0.5).sum())).to_string())
print(X[X.f12_ultimo>-0.5].sort_values('f12_ultimo',ascending=False)[['t','name','date','px','p52','f12_ultimo']].head(25).to_string())
X.to_pickle(f'{A}/fallimenti.pkl')
# effetto sui rapporti se si usa l'ultimo prezzo per queste righe
H['f12x']=H.f12
m=pd.MultiIndex.from_frame(H[['t','date']]); fx=X.set_index(['t','date']).f12_ultimo
v=fx.reindex(m).values; sel=(~np.isnan(v))&(v>-0.5)
H.loc[sel,'f12x']=v[sel]
for c in ['f12','f12x']:
    H['cr']=H[c]<=-0.5
    print(c,' '.join(f"{b}: {H[H.blocco==b][H[H.blocco==b].p52<0.4].cr.mean()/H[H.blocco==b].cr.mean():.2f} esc/amm {H[H.blocco==b][H[H.blocco==b].p52<0.4].cr.mean():.3f}/{H[H.blocco==b][H[H.blocco==b].p52>=0.4].cr.mean():.3f}" for b in ['2000-03','2004-07','2008-11']))
