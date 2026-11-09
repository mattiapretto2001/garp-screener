# Guadagni finti: righe con f12 >= +100% il cui salto piu' grande e' un giorno solo senza reazione del volume / frazionamento
import sys, os, json, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
from world_04_features import clean
O=f'{ML}/storico5'; A='${RICERCA_BASE}/avvA'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H=U[U.storico]
X=H[H.f12>=1.0]
pool,src=P9.series_pool()
def spl(t):
    fn=f'{O}/splits_A/{t}.json'
    if not os.path.exists(fn): return []
    out=[]
    for s in json.load(open(fn)):
        try: a,b=s['split'].split('/'); out.append((pd.Timestamp(s['date']), float(a)/float(b)))
        except Exception: pass
    return out
rows=[]
for t,g in X.groupby('t'):
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index(); d=d[(d.c>0)&d.a.notna()]
    aa,_=clean(d); lr=np.log(aa).diff(); v=d.v.values.astype(float); sp=spl(t)
    for _,r in g.iterrows():
        t1=r.date+pd.offsets.MonthEnd(12)
        w=lr[(lr.index>r.date)&(lr.index<=t1)]
        if not len(w): continue
        day=w.idxmax(); j=w[day]; k=d.index.get_loc(day); i=d.index.searchsorted(r.date,side='right')-1
        b=v[max(0,k-21):k]; b=b[b>0]; vd=v[k]/np.median(b) if len(b) else np.nan
        zb=(v[max(0,k-20):k]==0).mean()
        near=[f for ds,f in sp if abs((ds-day).days)<=3]
        # rendimento senza quel giorno
        f12x=np.exp(np.log1p(r.f12)-j)-1 if r.f12>-0.999 else r.f12
        rows.append(dict(t=t,date=r.date,f12=r.f12,giorno=day,salto=np.exp(j)-1,vol_giorno=vd,zero_prima=zb,split_api=near[0] if near else np.nan,f12_senza=f12x,src=r.src,p52=r.p52))
R=pd.DataFrame(rows); R.to_pickle(f'{A}/guadagni.pkl')
big=R[R.salto>=0.8]
sus=big[(big.vol_giorno<2)|big.split_api.notna()|(big.zero_prima>=0.5)]
print('righe f12>=100%:',len(R),'| salto di un giorno >=+80%:',len(big),'| sospetti (volume <2x, frazionamento, volume zero prima):',len(sus),sus.t.nunique(),'titoli')
pd.set_option('display.width',250)
print(sus.drop_duplicates('t').sort_values('salto',ascending=False)[['t','date','f12','giorno','salto','vol_giorno','zero_prima','split_api','f12_senza','src','p52']].head(40).to_string())
