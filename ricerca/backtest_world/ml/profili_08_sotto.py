# profili_08: controllo dentro i profili eterogenei (punteggio M0 fuori campione, 2015-2026)
#  PREPROF: 'veri' pre-utile (in perdita in almeno 3 degli ultimi 5 anni) contro perdite 'temporanee' (al massimo 1 anno in perdita su 5)
#  TEMI: settori esclusi (energia, materie prime, servizi pubblici) contro industrie emergenti
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
F = fv3.load(cols=['n_loss_5y', 'sector'])
rows = []
subs = {'PREPROF': {'veri (>=3 anni in perdita su 5)': F.n_loss_5y >= 3, 'temporanei (<=1 su 5)': F.n_loss_5y <= 1},
        'TEMI': {'settori esclusi': F.sector.astype(str).isin(COMMOD_SECT), 'industrie emergenti': ~F.sector.astype(str).isin(COMMOD_SECT)}}
for k, D in subs.items():
    for nm, m in D.items():
        s = SC[k]['M0'].astype(float); s = s[m.reindex(s.index).fillna(False).values]; X = B.loc[s.index]
        q = s.groupby(X.date).rank(pct=True)
        ic = ic_matrix(q.to_frame('s'), X.rk12_reg, X.date, min_n=20)['s']
        U = X.groupby('date').r_eur.mean(); r5 = X[q > 0.8].groupby('date').r_eur.mean().reindex(U.index).fillna(0)
        r1 = X[q <= 0.2].groupby('date').r_eur.mean().reindex(U.index).fillna(0)
        v = X.top5_reg.notna(); hi = q > 0.8
        rows.append(dict(profilo=k, sotto=nm, n_med=X.groupby('date').size().median(), ic=ic.mean(), t=nwt(ic),
                         Q5_U=cagr_q(r5) - cagr_q(U), Q1_U=cagr_q(r1) - cagr_q(U), U=cagr_q(U), ecc_Q5=X.top5_reg[v & hi].mean(), ecc=X.top5_reg[v].mean(),
                         dis_Q5=X.bot20_reg[v & hi].mean(), dis=X.bot20_reg[v].mean(), crollo_Q5=X.crash50[v & hi].mean(), crollo=X.crash50[v].mean()))
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/sotto_profili.csv', index=False); pd.set_option('display.width', 250)
print(T.round(3).to_string(index=False))
