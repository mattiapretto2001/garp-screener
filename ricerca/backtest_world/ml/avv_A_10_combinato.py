import pandas as pd, numpy as np
O='${RICERCA_BASE}/backtest_world/ml/storico5'
A='${RICERCA_BASE}/avvA'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H=U[U.storico].copy()
S=pd.read_pickle(f'{A}/salti_class2.pkl'); S=S[S.innesto|S.split_api.notna()|(S.vol_giorno<2)]
G=pd.read_pickle(f'{A}/guadagni.pkl'); G=G[(G.salto>=0.8)&((G.vol_giorno<2)|G.split_api.notna()|(G.zero_prima>=0.5))]
k=pd.MultiIndex.from_frame(H[['t','date']])
a=S.set_index(['t','date']).f12_tronco.reindex(k).values; b=G.set_index(['t','date']).f12_senza.reindex(k).values
H['f12c']=np.clip(np.where(~np.isnan(a),a,np.where(~np.isnan(b),b,H.f12.values)),-1,10)
print('righe corrette: crolli finti',int((~np.isnan(a)).sum()),'guadagni finti',int((~np.isnan(b)).sum()))
ew=lambda X,c: X.groupby('date')[c].mean().mean()
for c in ['f12','f12c']:
    R=H[(H.date>='2008-12-31')&(H.date<='2009-06-30')]; s=R.p52<0.4
    print(c,'| tutto 2000-11 ew',round(ew(H,c),4),'mediana',round(H[c].median(),4),'| sopravvissute',round(ew(H[~H.uscita_pre2011],c),4),
          '| rimbalzo sotto40',round(R[s][c].mean(),3),'sopra90',round(R[R.p52>=0.9][c].mean(),3),'tutti',round(ew(R,c),3),'ammessi',round(ew(R[~s],c),3))
    for bl in ['2000-03','2004-07','2008-11']:
        X=H[H.blocco==bl]; s=X.p52<0.4
        print('   ',bl,'ew',round(ew(X,c),4),'ew ammessi',round(ew(X[~s],c),4),'diff',round(ew(X[~s],c)-ew(X,c),4),'sotto40 media',round(X[s][c].mean(),3),'mediana',round(X[s][c].median(),3))
    X=H; s=X.p52<0.4; print('    sotto40 2000-11 media',round(X[s][c].mean(),3),'mediana',round(X[s][c].median(),3),'| sopra90 media',round(X[X.p52>=0.9][c].mean(),3))
