# avv_uni_01: le societa' uscite dal listino sono davvero presenti nel 2012-2016? Ultima data nel pannello per le delisted.
import numpy as np, pandas as pd
import fv3
F = fv3.load(cols=['t','date','reg','reg_rob','delisted','delist12','bankrupt12','fwd12_loc','mcap_usd'])
L = F.groupby('t').agg(last=('date','max'), first=('date','min'), delisted=('delisted','first'), reg=('reg_rob','first'))
D = L[L.delisted.astype(bool)]
print('societa delisted:', len(D), ' su', len(L))
print('anno dell\'ultima data nel pannello (delisted) per regione:')
print(pd.crosstab(D['last'].dt.year, D.reg))
print('\nnumero di societa presenti per anno (prima data) e regione:')
print(pd.crosstab(L['first'].dt.year, L.reg))
# quante societa' per data, per regione
n = F.groupby(['date','reg_rob'],observed=True).size().unstack()
print(n.iloc[::4])
# uscite nei 12 mesi per anno (USA)
F['y'] = F.date.dt.year
print(F[F.reg=='USA'].groupby('y')[['delist12','bankrupt12']].mean().round(4))
