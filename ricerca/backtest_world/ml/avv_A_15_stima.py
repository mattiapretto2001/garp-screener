# Effetto delle societa' aggiunte con i volumi corretti (stima e prudente): v2 contro v2 senza serie nuove
import sys, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'; O=f'{ML}/storico5'
sys.path.insert(0, ML)
from sA_common import build, finish
P=pd.read_pickle(f'{O}/pannello_prezzi_us_v2.pkl'); P=P[P.date<='2011-09-30'].reset_index(drop=True)
C=pd.read_pickle(f'{O}/volumi_corretti_A.pkl').set_index(['t','date'])
j=C.reindex(pd.MultiIndex.from_frame(P[['t','date']]))
Pv=P.copy(); hv=j.dv63_v.notna().values; Pv.loc[hv,'dv63']=j.dv63_v.values[hv]; Pv.loc[hv,'px']=j.px_v.values[hv]
Pp=P.copy(); has=j.dv_raw.notna().values
Pp.loc[has,'dv63']=np.minimum(P.dv63.values[has], j.dv_raw.values[has]); Pp.loc[has,'px']=np.minimum(P.px.values[has], j.px_p.values[has])
ew=lambda X: X.groupby('date').f12.mean().mean()
def rep(lab,U):
    H=U[U.storico]; s=H.p52<0.4
    r=[H[H.blocco==b] for b in ['2000-03','2004-07','2008-11']]
    print(f'{lab:22s} titoli/data {len(H)/H.date.nunique():6.0f} uscite {H.uscita_pre2011.mean():.3f} crolli {H.L50.mean():.4f} ew {ew(H):.4f} '
          f'sopravv {ew(H[~H.uscita_pre2011]):.4f} rapporti '+' '.join(f'{X[X.p52<0.4].L50.mean()/X.L50.mean():.2f}' for X in r))
for lab,PP in [('completo',P),('stima',Pv),('prudente',Pp)]:
    U=build(PP); U['nuova']=U.src.isin(['V','W'])
    rep(lab,U); rep(lab+' senza nuove',finish(U[~U.nuova]))
