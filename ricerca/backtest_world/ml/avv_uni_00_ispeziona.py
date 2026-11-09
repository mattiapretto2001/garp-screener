# avv_uni_00 (verifica avversariale, 07/11): ispezione di base della matrice usata da univariata_*.py
import numpy as np, pandas as pd
from univariata_common import *
F = load_dev()
print('righe', len(F), 'date', F.date.nunique(), F.date.min(), F.date.max())
print('reg:', F.reg.value_counts().to_dict())
print('reg_rob:', F.reg_rob.value_counts().to_dict())
print('quota per reg_rob per data media:', (F.groupby(['date','reg_rob'],observed=True).size().groupby('reg_rob').mean()).round(0).to_dict())
print('mcap_usd min / quantili:', F.mcap_usd.min(), F.mcap_usd.quantile([.01,.05,.1,.25,.5]).round(-6).to_dict())
print('adv_usd quantili:', F.adv_usd.quantile([.01,.05,.1,.5]).round(-3).to_dict())
# look-ahead: data di disponibilita' del bilancio <= data
fa = pd.to_datetime(F.fin_av)
print('fin_av > date:', int((fa > F.date).sum()), 'fin_av mancante:', int(fa.isna().sum()))
print('fin_end > date:', int((pd.to_datetime(F.fin_end) > F.date).sum()))
# rendimenti esattamente zero (possibile riga mancante in rq2 riempita con 0)
print('fwd12_loc == 0 esatto:', int((F.fwd12_loc == 0).sum()), ' delist12 quota', round(F.delist12.mean(),3), ' bankrupt12', round(F.bankrupt12.mean(),4))
print('quota delisted (esito finale) per reg_rob e periodo:')
print(F.groupby(['reg_rob','per3'],observed=True).delisted.mean().unstack().round(3))
print('delist12 per reg_rob e periodo:')
print(F.groupby(['reg_rob','per3'],observed=True).delist12.mean().unstack().round(3))
# copertura variabili chiave per regione
V=['dsh3','n_beat4','n_est4','surp_mean4','runway_y','fcfy','roic','hist_y','age_y','opm_std5','capex_int','fin_age_d','rd_int','gm_std5']
print(F.groupby('reg_rob',observed=True)[V].apply(lambda d: d.notna().mean()).round(2).T)
# ext_fields fuori USA e societa' uscite
nu = F.reg != 'USA'
print('fuori USA: quota ext_fields', round(F[nu].ext_fields.mean(),3))
print('fuori USA, delisted fra ext_fields / non ext:', round(F[nu & F.ext_fields].delisted.mean(),3), round(F[nu & ~F.ext_fields].delisted.mean(),3))
print('fuori USA, n_beat4 presente: quota ext', round(F[nu & F.n_beat4.notna()].ext_fields.mean(),3), 'n righe', int((nu & F.n_beat4.notna()).sum()))
print('fuori USA, rk12 medio ext vs non ext:', round(F[nu & F.ext_fields].rk12_reg.mean(),3), round(F[nu & ~F.ext_fields].rk12_reg.mean(),3))
print('USA: n_beat4 presente per delisted:', F[F.reg=='USA'].groupby('delisted').n_beat4.apply(lambda s: s.notna().mean()).round(3).to_dict())
print('USA: n_est4 medio per delisted:', F[F.reg=='USA'].groupby('delisted').n_est4.mean().round(2).to_dict())
print(F.n_est4.value_counts().sort_index().to_dict())
print(pd.crosstab(F.n_est4, F.n_beat4))
