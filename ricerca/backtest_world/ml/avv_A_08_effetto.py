# Effetto dei crolli finti sui numeri chiave: f12 troncato al giorno prima del salto sospetto
import pandas as pd, numpy as np
O='${RICERCA_BASE}/backtest_world/ml/storico5'
A='${RICERCA_BASE}/avvA'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H=U[U.storico].copy()
S=pd.read_pickle(f'{A}/salti_class2.pkl')
S['sosp']=S.innesto|S.split_api.notna()|(S.vol_giorno<2)
fix=S[S.sosp].set_index(['t','date']).f12_tronco
k=pd.MultiIndex.from_frame(H[['t','date']])
nf=fix.reindex(k).values
H['f12c']=np.where(np.isnan(nf),H.f12.values,np.clip(nf,-1,10))
print('righe corrette',int((~np.isnan(nf)).sum()),'| crolli tolti',int(((H.f12<=-0.5)&(H.f12c>-0.5)).sum()),'| -100% tolti',int(((H.f12<=-0.999)&(H.f12c>-0.999)).sum()))
ew=lambda X,c: X.groupby('date')[c].mean().mean()
for c in ['f12','f12c']:
    H['cr']=H[c]<=-0.5
    out=[]
    for b in ['2000-03','2004-07','2008-11']:
        X=H[H.blocco==b]; s=X.p52<0.4
        out.append(f"{b}: crolli {X.cr.mean():.3f} rapp {X[s].cr.mean()/X.cr.mean():.2f} esc/amm {X[s].cr.mean():.3f}/{X[~s].cr.mean():.3f} sopra90 {X[X.p52>=0.9].cr.mean():.3f} ew {ew(X,c):+.3f}")
    s=H.p52<0.4
    print(c,'| tutti crolli',round(H.cr.mean(),4),'ew',round(ew(H,c),4),'rapp',round(H[s].cr.mean()/H.cr.mean(),2),'| -100%',round((H[c]<=-0.999).mean(),4))
    print('   '+'\n   '.join(out))
    Y=H[(H.date>='2007-09-30')&(H.date<='2008-12-31')]; s=Y.p52<0.4
    print('   crisi 2008 sotto40/sopra90',round(Y[s].cr.mean(),3),round(Y[Y.p52>=0.9].cr.mean(),3))
    S2=H[~H.uscita_pre2011]; print('   sopravvissute ew',round(ew(S2,c),4),'crolli',round(S2.cr.mean(),4),'| uscite crolli',round(H[H.uscita_pre2011].cr.mean(),4))
    for col in ['vol','mom12']:
        Y=H[H[col].notna()].copy(); Y['d']=Y.groupby('date')[col].transform(lambda z: pd.qcut(z.rank(method='first'),10,labels=False)+1)
        g=Y.groupby('d'); print('  ',col,'crolli d1/d10',round(g.cr.mean()[1],3),round(g.cr.mean()[10],3),'f12 d10',round(g[c].mean()[10],4),'centro',round(Y[Y.d.isin([5,6])][c].mean(),4))
# per fascia p52 dei crolli tolti
H['tolto']=(H.f12<=-0.5)&(H.f12c>-0.5)
print('crolli tolti per fascia p52:',H[H.tolto].assign(b=pd.cut(H.p52,[0,.4,.6,.75,.9,1.01],right=False)).b.value_counts().sort_index().to_dict())
print('per blocco:',H[H.tolto].blocco.value_counts().to_dict(),'| per origine',H[H.tolto].src.value_counts().to_dict(), '| uscite pre2011', H[H.tolto].uscita_pre2011.mean().round(2))
