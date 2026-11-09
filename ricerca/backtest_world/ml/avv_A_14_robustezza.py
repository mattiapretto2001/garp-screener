import sys, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'; O=f'{ML}/storico5'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H=U[U.storico].copy()
ew=lambda X: X.groupby('date').f12.mean().mean()
# 1) rapporto per anno e quanti nomi
print('anno: quota sotto40, n righe sotto40, crolli sotto40, rapporto, guardia (ammessi - tutti)')
for y,X in H.groupby('anno'):
    s=X.p52<0.4
    print(y, round(s.mean(),3), int(s.sum()), int(X[s].L50.sum()), round(X[s].L50.mean()/X.L50.mean(),2), round(ew(X[~s])-ew(X),3))
for b in ['2000-03','2004-07','2008-11']:
    X=H[H.blocco==b]; s=X.p52<0.4
    print(b,'righe sotto40',int(s.sum()),'titoli distinti',X[s].t.nunique(),'crolli',int(X[s].L50.sum()))
# 2) bootstrap per data (blocchi di 4 trimestri consecutivi) del rapporto 2008-11 e 2000-03
rng=np.random.default_rng(0)
for b in ['2000-03','2004-07','2008-11']:
    X=H[H.blocco==b]; ds=sorted(X.date.unique())
    g=X.assign(s=X.p52<0.4).groupby('date').apply(lambda z: pd.Series({'cs':z[z.s].L50.sum(),'ns':z.s.sum(),'c':z.L50.sum(),'n':len(z)}))
    g=g.loc[ds].values; n=len(ds); out=[]
    for _ in range(4000):
        st=rng.integers(0,n-3,size=n//4+1); idx=np.concatenate([np.arange(s0,s0+4) for s0 in st])[:n]
        G=g[idx].sum(0); out.append((G[0]/G[1])/(G[2]/G[3]))
    print(b,'rapporto',round((g[:,0].sum()/g[:,1].sum())/(g[:,2].sum()/g[:,3].sum()),2),'intervallo 90% bootstrap a blocchi di 4 trimestri',np.round(np.quantile(out,[.05,.95]),2),'P(>=2)',round(np.mean(np.array(out)>=2),2))
# 3) bootstrap per titolo (cluster) per 2008-11
X=H[H.blocco=='2008-11'].assign(s=lambda z: z.p52<0.4)
g=X.groupby('t').apply(lambda z: pd.Series({'cs':z[z.s].L50.sum(),'ns':z.s.sum(),'c':z.L50.sum(),'n':len(z)})).values
out=[]
for _ in range(3000):
    G=g[rng.integers(0,len(g),len(g))].sum(0); out.append((G[0]/G[1])/(G[2]/G[3]))
print('2008-11 bootstrap per titolo, 90%:',np.round(np.quantile(out,[.05,.95]),2))
# 4) momentum senza 2000 e 2009
Y=H[H.mom12.notna()].copy(); Y['d']=Y.groupby('date').mom12.transform(lambda z: pd.qcut(z.rank(method='first'),10,labels=False)+1)
for lab,Z in [('tutti',Y),('senza 2000 e 2009',Y[~Y.anno.isin([2000,2009])])]:
    g=Z.groupby('d').f12.mean(); print('mom12',lab,'d1',round(g[1],3),'centro',round(Z[Z.d.isin([5,6])].f12.mean(),3),'d10',round(g[10],3))
# 5) rimbalzo: quanto pesa la coda
R=H[(H.date>='2008-12-31')&(H.date<='2009-06-30')]; s=R.p52<0.4; x=R[s].f12
print('rimbalzo sotto40: n',len(x),'media',round(x.mean(),3),'media senza 1% migliore',round(x[x<x.quantile(.99)].mean(),3),'senza 5%',round(x[x<x.quantile(.95)].mean(),3),'quota f12=+1000%',int((x>=9.99).sum()))
