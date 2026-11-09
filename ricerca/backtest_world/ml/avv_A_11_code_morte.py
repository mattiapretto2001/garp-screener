# "Code morte": serie di societa' uscite che continuano per anni con volume zero (o con un altro titolo innestato).
import sys, os, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, ML)
import s5_09_pannello_v2 as P9
O=f'{ML}/storico5'; A='${RICERCA_BASE}/avvA'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H=U[U.storico]
pool,src=P9.series_pool()
rows=[]
for t in H.t.unique():
    d=pool[t]; d=d[~d.index.duplicated(keep='last')].sort_index(); d=d[(d.c>0)&d.a.notna()]
    nz=(d.v.fillna(0).values>0).astype(float)
    fr=pd.Series(nz,index=d.index).rolling(60,min_periods=20).mean()
    ok=fr[fr>=0.5]
    lt=ok.index[-1] if len(ok) else d.index[-1]
    rows.append(dict(t=t,last=d.index[-1],ultimo_scambio=lt,coda_giorni=(d.index>lt).sum()))
Z=pd.DataFrame(rows).set_index('t'); Z.to_pickle(f'{A}/code_morte.pkl')
Z['coda']=Z.coda_giorni>=120
print('titoli',len(Z),'| con coda morta >=120 giorni di borsa:',Z.coda.sum())
H=H.assign(us=H.t.map(Z.ultimo_scambio))
H['uscita_vera']=H.us<pd.Timestamp('2011-06-30')
print('righe uscite prima di meta 2011: rapporto',round(H.uscita_pre2011.mean(),4),'| con la data dell ultimo scambio vero',round(H.uscita_vera.mean(),4))
x=H[H.uscita_vera&~H.uscita_pre2011]; print('righe riclassificate',len(x),'titoli',x.t.nunique()); print(x.drop_duplicates('t')[['t','name','last','us']].head(25).to_string())
ew=lambda X: X.groupby('date').f12.mean().mean()
print('sopravvissute: rapporto',round(ew(H[~H.uscita_pre2011]),4),round(H[~H.uscita_pre2011].L50.mean(),4),'| vere',round(ew(H[~H.uscita_vera]),4),round(H[~H.uscita_vera].L50.mean(),4),'| tutte',round(ew(H),4))
