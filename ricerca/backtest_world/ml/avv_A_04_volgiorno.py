import sys, os, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
from world_04_features import clean
A='${RICERCA_BASE}/avvA'
R=pd.read_pickle(f'{A}/salti.pkl')
S=R[((R.f12<=-0.5)&(R.salto<=-0.45))|((R.f12>=1.5)&(R.salto>=0.8))]
pool,src=P9.series_pool()
ev={}
for t in S.t.unique():
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index(); d=d[(d.c>0)&d.a.notna()]
    v=d.v.values.astype(float); c=d.c.values.astype(float)
    for day in S[S.t==t].giorno.unique():
        k=d.index.get_loc(day)
        b=v[max(0,k-21):k]; a=v[k+1:k+21]; b=b[b>0]; a=a[a>0]
        vd=v[k]/np.median(b) if len(b) else np.nan
        pp=np.median(a)/np.median(b) if len(a) and len(b) else np.nan
        cr=c[k]/c[k-1]
        ev[(t,day)]=(vd,pp,cr)
S=S.assign(vol_giorno=[ev[(t,g)][0] for t,g in zip(S.t,S.giorno)], vol_dopo_prima=[ev[(t,g)][1] for t,g in zip(S.t,S.giorno)],
           salto_chiusura=[ev[(t,g)][2]-1 for t,g in zip(S.t,S.giorno)])
S.to_pickle(f'{A}/salti_vol.pkl')
c=S[S.f12<=-0.5]
print('crolli con un giorno <=-45%:',len(c),'eventi',c[['t','giorno']].drop_duplicates().shape[0])
print('volume del giorno / mediana 20 gg prima, quantili:',c.vol_giorno.quantile([.1,.25,.5,.75]).round(2).to_dict())
sus=c[(c.vol_giorno<2)]
print('sospetti (volume del giorno < 2x):',len(sus),'righe,',sus[['t','giorno']].drop_duplicates().shape[0],'eventi')
print(sus.drop_duplicates(['t','giorno']).sort_values('salto')[['t','date','f12','giorno','salto','salto_chiusura','vol_giorno','vol_dopo_prima','split_api','src']].head(60).to_string())
