import pandas as pd, numpy as np
A='${RICERCA_BASE}/avvA'
S=pd.read_pickle(f'{A}/salti_class.pkl')
r=1+S.salto
fr=np.array([1/2,1/3,2/3,1/4,1/5,1/10,1/8,1/6,1/1.5])
def near(x,tol):
    return np.min(np.abs(np.log(x)-np.log(fr))) < tol
for tol in [0.01,0.02]:
    m=r.apply(lambda x: near(x,tol))
    # controllo: stesse finestre spostate del 6% (densita' "di fondo")
    m2=r.apply(lambda x: near(x*1.06,tol)); m3=r.apply(lambda x: near(x/1.06,tol))
    print('tolleranza',tol,'| righe vicine a una frazione semplice',m.sum(),'| finestre spostate +6%/-6%:',m2.sum(),m3.sum())
S['frazione']=r.apply(lambda x: near(x,0.015))
S['sospetto']=S.innesto|S.split_api.notna()|(S.vol_giorno<2)|S.frazione
print('sospetti',S.sospetto.sum(),'su',len(S),'| dopo il troncamento restano crolli',(S[S.sospetto].f12_tronco<=-0.5).sum())
S.to_pickle(f'{A}/salti_class2.pkl')
