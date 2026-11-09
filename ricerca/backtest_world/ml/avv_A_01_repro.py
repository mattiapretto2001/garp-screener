# Verifica avversariale prova A: ricalcolo indipendente di alcuni numeri dal file universo v2
import pandas as pd, numpy as np
O='${RICERCA_BASE}/backtest_world/ml/storico5'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl')
H=U[U.storico].copy()
print('righe',len(H),'date',H.date.nunique(),'titoli/data',round(len(H)/H.date.nunique(),1),'uscite pre2011',round(H.uscita_pre2011.mean(),4))
H['crash']=H.f12<=-0.5
def ew(X): return X.groupby('date').f12.mean().mean()
for b in ['2000-03','2004-07','2008-11',None]:
    X=H if b is None else H[H.blocco==b]
    s=X.p52<0.4
    print(b,'crolli',round(X.crash.mean(),4),'ew',round(ew(X),4),'ratio',round(X[s].crash.mean()/X.crash.mean(),3),
          'esclusi/ammessi',round(X[s].crash.mean(),3),round(X[~s].crash.mean(),3),'ew ammessi',round(ew(X[~s]),4),'-100%',round((X.f12<=-0.999).mean(),4))
R=H[(H.date>='2008-12-31')&(H.date<='2009-06-30')]; s=R.p52<0.4
print('rimbalzo quota',round(s.mean(),3),'f12 sotto40',round(R[s].f12.mean(),3),'mediana',round(R[s].f12.median(),3),'sopra90',round(R[R.p52>=0.9].f12.mean(),3),'ew tutti',round(ew(R),3),'ew ammessi',round(ew(R[~s]),3))
# decili vol e mom12 (mia versione: qcut sul rank per data)
for col in ['vol','mom12']:
    Y=H[H[col].notna()].copy()
    Y['d']=Y.groupby('date')[col].transform(lambda z: pd.qcut(z.rank(method='first'),10,labels=False)+1)
    g=Y.groupby('d')
    print(col,'crolli d1/d10',round(g.crash.mean()[1],4),round(g.crash.mean()[10],4),'f12 d1/d10',round(g.f12.mean()[1],4),round(g.f12.mean()[10],4),'centro',round(Y[Y.d.isin([5,6])].f12.mean(),4))
S=H[~H.uscita_pre2011]; print('sopravvissute ew',round(ew(S),4),'crolli',round(S.crash.mean(),4))
