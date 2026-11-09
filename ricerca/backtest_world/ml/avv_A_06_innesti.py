# Crolli finti: serie "innestate" (codice riusato: prezzo da 30 $ a pochi centesimi in un giorno, poi volume zero)
# e frazionamenti/scorpori corretti male (un giorno da -80/-97% senza reazione del volume, con frazionamento API vicino).
import sys, os, json, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
from world_04_features import clean
A='${RICERCA_BASE}/avvA'
S=pd.read_pickle(f'{A}/salti_vol.pkl'); S=S[S.f12<=-0.5]
pool,src=P9.series_pool()
info={}
for t in S.t.unique():
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index(); d=d[(d.c>0)&d.a.notna()]
    aa,_=clean(d); v=d.v.values.astype(float); c=d.c.values.astype(float)
    for _,r in S[S.t==t].iterrows():
        k=d.index.get_loc(r.giorno); i=d.index.searchsorted(r.date,side='right')-1
        z=(v[k+1:k+21]==0).mean() if k+1<len(v) else 1.0
        info[(t,r.date)]=(z, aa.values[k-1]/aa.values[i]-1, c[k-1], c[k])
S['zero_dopo']=[info[(t,d)][0] for t,d in zip(S.t,S.date)]
S['f12_tronco']=[info[(t,d)][1] for t,d in zip(S.t,S.date)]
S['c_prima']=[info[(t,d)][2] for t,d in zip(S.t,S.date)]; S['c_dopo']=[info[(t,d)][3] for t,d in zip(S.t,S.date)]
S['innesto']=S.zero_dopo>=0.5
S['fraz_male']=(~S.innesto)&S.split_api.notna()&(S.vol_giorno<2.5)
S.to_pickle(f'{A}/salti_class.pkl')
print('crolli con giorno <=-45%:',len(S),'| innesti (volume zero dopo >=50%):',S.innesto.sum(),'righe,',S[S.innesto].t.nunique(),'titoli',
      '| frazionamenti corretti male:',S.fraz_male.sum(),'righe')
print('innesti per origine:',S[S.innesto].src.value_counts().to_dict())
print('innesti: f12 troncato prima del salto, crollo vero?',(S[S.innesto].f12_tronco<=-0.5).mean().round(3))
print(S[S.innesto].drop_duplicates('t').sort_values('date')[['t','date','f12','f12_end','giorno','c_prima','c_dopo','zero_dopo','f12_tronco','src']].to_string())
