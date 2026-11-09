# Tutte e tre le correzioni insieme: crolli finti (innesti, frazionamenti/scorpori), guardagni finti, regola -100% su chi compra gia' a terra
import pandas as pd, numpy as np
O='${RICERCA_BASE}/backtest_world/ml/storico5'
A='${RICERCA_BASE}/avvA'
U=pd.read_pickle(f'{O}/universo_prezzi_us_v2.pkl'); H=U[U.storico].copy()
S=pd.read_pickle(f'{A}/salti_class2.pkl'); S=S[S.innesto|S.split_api.notna()|(S.vol_giorno<2)]
G=pd.read_pickle(f'{A}/guadagni.pkl'); G=G[(G.salto>=0.8)&((G.vol_giorno<2)|G.split_api.notna()|(G.zero_prima>=0.5))]
F=pd.read_pickle(f'{A}/fallimenti.pkl'); F=F[F.f12_ultimo>-0.5]
k=pd.MultiIndex.from_frame(H[['t','date']])
a=S.set_index(['t','date']).f12_tronco.reindex(k).values; b=G.set_index(['t','date']).f12_senza.reindex(k).values; c=F.set_index(['t','date']).f12_ultimo.reindex(k).values
H['f12c']=np.clip(np.where(~np.isnan(a),a,np.where(~np.isnan(c),c,np.where(~np.isnan(b),b,H.f12.values))),-1,10)
n=(~np.isnan(a))|(~np.isnan(b))|(~np.isnan(c)); print('righe corrette',int(n.sum()),f'({n.mean():.2%})','| crolli prima/dopo',int((H.f12<=-0.5).sum()),int((H.f12c<=-0.5).sum()),'| -100% prima/dopo',int((H.f12<=-0.999).sum()),int((H.f12c<=-0.999).sum()))
ew=lambda X,c: X.groupby('date')[c].mean().mean()
for col in ['f12','f12c']:
    H['cr']=H[col]<=-0.5; s=H.p52<0.4
    line=[f'crolli {H.cr.mean():.3f}', f'ew {ew(H,col):+.3f}', f'sopravv {ew(H[~H.uscita_pre2011],col):+.3f}']
    for bl in ['2000-03','2004-07','2008-11']:
        X=H[H.blocco==bl]; s=X.p52<0.4
        line.append(f'{bl}: {X[s].cr.mean()/X.cr.mean():.2f} ({X[s].cr.mean():.3f}/{X[~s].cr.mean():.3f}, guardia {ew(X[~s],col)-ew(X,col):+.3f})')
    R=H[(H.date>='2008-12-31')&(H.date<='2009-06-30')]; s=R.p52<0.4
    line.append(f'rimbalzo {R[s][col].mean():+.2f}/{R[R.p52>=0.9][col].mean():+.2f}, mercato {ew(R,col):+.2f} senza esclusi {ew(R[~s],col):+.2f}')
    print(col,' | '.join(line))
s=H.p52<0.4
for col in ['f12','f12c']:
    print(col,'sotto40 2000-11: crolli',round((H[s][col]<=-0.5).mean(),3),'mediana',round(H[s][col].median(),3),'media',round(H[s][col].mean(),3))
print('quota righe sotto40 del 2008-11 che cadono nel 2008-09:', round(((H.blocco=='2008-11')&s&H.anno.isin([2008,2009])).sum()/((H.blocco=='2008-11')&s).sum(),3))
