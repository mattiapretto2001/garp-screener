# avv_prof_03 (verifica avversariale): il punteggio M0 e' davvero "per profilo"? Confronto fuori campione 2015-2026 con:
#  - PREZZO: solo mom12_1, hi52, vol1y (tre variabili di prezzo presenti in tutti i profili)
#  - FONDAMENTALI: le candidate del profilo senza le tre di prezzo
#  - TUTTE76: tutte le 76 variabili ammesse con direzione a priori != 0, pesi uguali (nessuna scelta di candidate)
#  - SENZA CAMPI ESTESI: candidate senza gm, gpa, d_gm, gm_std5, sga_int, n_beat4, surp_mean4 (fuori USA scelti a posteriori)
#  - incrocio: lista del profilo j applicata al profilo i
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from profili_common import *
O2 = f'{HERE}/avv_prof_out'
B = pd.read_pickle(f'{OUT}/base.pkl')
cg = lambda r: (1 + r).prod() ** (4 / len(r)) - 1
PRICE = ['mom12_1', 'hi52', 'vol1y']
EXTF = ['gm', 'gpa', 'd_gm', 'gm_std5', 'sga_int', 'n_beat4', 'surp_mean4']
TECH = ['fin_age_d', 'n_est4', 'logmcap', 'log_adv', 'ind_n']
ALL76 = [c for c in fv3.PREDICTORS if c not in TECH and fv3.DIRECTION.get(c, 0) != 0]


def meas(X, s):
    q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5); U = X.groupby('date').r_eur.mean()
    r5 = X[q == 5].groupby('date').r_eur.mean().reindex(U.index); r1 = X[q == 1].groupby('date').r_eur.mean().reindex(U.index)
    Zr = s.groupby(X.date).rank(pct=True).to_frame('s'); ic = ic_matrix(Zr, X.rk12_reg, X.date)['s']
    return dict(IC=ic.mean(), t_IC=nwt(ic), Q5_U=cg(r5) - cg(U), Q1_U=cg(r1) - cg(U), arit_Q5_U=(r5 - U).mean() * 4, t_arit=nwt(r5 - U, 2))


rows, cross = [], {}
for k in PNAME:
    Z = pd.read_pickle(f'{OUT}/Z_{k}.pkl'); X = B.loc[Z.index]; oos = (X.date.dt.year >= 2015).values
    Z, X = Z[oos], X[oos]
    # rango di ALL76 con segno: Z e' gia' col segno a priori (rank_in), quindi basta la media
    V = {'M0 (autore)': CAND[k], 'PREZZO (3 var.)': PRICE, 'FONDAMENTALI (M0 senza prezzo)': [c for c in CAND[k] if c not in PRICE],
         'TUTTE76 (nessuna scelta)': ALL76, 'M0 senza campi estesi': [c for c in CAND[k] if c not in EXTF]}
    for nm, cols in V.items():
        rows.append(dict(profilo=k, punteggio=nm, n_var=len(cols), **meas(X, (Z[cols] - 0.5).mean(axis=1))))
    # campi estesi solo USA: fuori USA valgono 0,5 (neutro), cosi' la scelta a posteriori non entra
    Zu = Z[CAND[k]].copy(); nonus = ~X.reg_rob.isin(['USA grandi', 'USA piccole/medie']).values
    for c in [c for c in CAND[k] if c in EXTF]: Zu.loc[nonus, c] = 0.5
    rows.append(dict(profilo=k, punteggio='M0 campi estesi solo USA', n_var=len(CAND[k]), **meas(X, (Zu - 0.5).mean(axis=1))))
    for j in PNAME:
        m = meas(X, (Z[CAND[j]] - 0.5).mean(axis=1)); cross[(k, j)] = (m['IC'], m['Q5_U'])
R = pd.DataFrame(rows); R.to_csv(f'{O2}/03_alternative.csv', index=False); pd.set_option('display.width', 250)
print(R.round(3).to_string(index=False))
C = pd.Series({k: v[0] for k, v in cross.items()}).unstack(); C5 = pd.Series({k: v[1] for k, v in cross.items()}).unstack()
print('\nIC fuori campione: righe = profilo su cui si misura, colonne = lista di variabili usata'); print(C.round(3).to_string())
print('\nQ5-U (punti/anno)'); print((C5 * 100).round(1).to_string())
C.to_csv(f'{O2}/03_incrocio_ic.csv'); C5.to_csv(f'{O2}/03_incrocio_q5.csv')
