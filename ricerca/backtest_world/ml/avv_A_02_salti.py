# Crolli e rendimenti estremi dovuti a un solo giorno (frazionamenti non corretti nel prezzo corretto?)
import sys, os, json, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
from world_04_features import clean
O=f'{ML}/storico5'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H=U[U.storico]
X=H[(H.f12<=-0.5)|(H.f12>=1.5)]
need=set(X.t)
pool,src=P9.series_pool()
def spl(t):
    fn=f'{O}/splits_A/{t}.json'
    if not os.path.exists(fn): return []
    out=[]
    for s in json.load(open(fn)):
        try:
            a,b=s['split'].split('/'); out.append((pd.Timestamp(s['date']), float(a)/float(b)))
        except Exception: pass
    return out
rows=[]
for t,g in X.groupby('t'):
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index(); d=d[(d.c>0)&d.a.notna()]
    aa,_=clean(d); lr=np.log(aa).diff()
    sp=spl(t)
    for _,r in g.iterrows():
        t1=r.date+pd.offsets.MonthEnd(12)
        w=lr[(lr.index>r.date)&(lr.index<=t1)]
        if not len(w): continue
        k=w.abs().idxmax(); j=w[k]
        tot=np.log1p(r.f12) if r.f12>-0.999 else np.nan
        near=[f for ds,f in sp if abs((ds-k).days)<=3]
        rows.append(dict(t=t,date=r.date,f12=r.f12,end=r.f12_end,giorno=k,salto=np.exp(j)-1,quota=(j/tot if tot==tot and tot!=0 else np.nan),
                         split_api=near[0] if near else np.nan, src=r.src))
R=pd.DataFrame(rows)
R.to_pickle('${RICERCA_BASE}/avvA/salti.pkl')
c=R[R.f12<=-0.5]; w=R[R.f12>=1.5]
print('righe crollo',len(c),'| con un giorno da -45% o peggio',(c.salto<=-0.45).sum(),'| di cui con frazionamento API entro 3 giorni',((c.salto<=-0.45)&c.split_api.notna()).sum())
s=c[(c.salto<=-0.45)&c.split_api.notna()]
print(s.assign(prodotto=(1+s.salto)*s.split_api).sort_values('salto').head(40).to_string())
print('righe +150%',len(w),'| con un giorno da +80% o piu',(w.salto>=0.8).sum(),'| con frazionamento API',((w.salto>=0.8)&w.split_api.notna()).sum())
s=w[(w.salto>=0.8)&w.split_api.notna()]
print(s.assign(prodotto=(1+s.salto)*s.split_api).sort_values('salto',ascending=False).head(30).to_string())
