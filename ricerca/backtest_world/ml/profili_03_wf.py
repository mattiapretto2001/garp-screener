# profili_03: punteggi per profilo costruiti in walk-forward (stima fino a 4 trimestri prima dell'anno di prova, prova sull'anno: 2015-2026)
# 4 metodi dichiarati prima:
#  M0 PRIORI  : pesi uguali sulle variabili candidate del profilo, segno a priori (nessuna stima)
#  M1 SCELTE  : fra 76 variabili (81 meno 5 tecniche) tiene quelle con |t| NW >=3 sul rango a 12 mesi dentro il profilo nella finestra di stima
#               (max 10, se nessuna: |t|>=2 max 5), pesi uguali col segno stimato
#  M2 REGR    : coefficienti medi della regressione multipla (Fama-MacBeth) sulle candidate, target rango
#  M3 CODE    : z(previsione eccezionale) - z(previsione disastro), regressioni multiple sulle candidate
# aggiunti DOPO aver visto che il rango migliora ma la media no (dichiarati come prove a posteriori):
#  M4 PULITE  : fra le 76 variabili, quelle che nella finestra di stima alzano il rango (t>=2) SENZA ridurre gli eccezionali (t>=0)
#               e senza aumentare i disastri (t<=0); max 8, pesi uguali, segno stimato (se nessuna: M0)
#  M5 MEDIA   : regressione multipla sulle candidate con target il rendimento in eccesso sulla regione tagliato 1-99% per data (la media)
# Misure fuori campione: IC del punteggio, quota eccezionali/disastri nel decimo migliore, portafogli top 10 / top 20 (netti 0,5%) contro
# l'universo del profilo (lordo) e contro scelte a caso.
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl')
TECH = ['fin_age_d', 'n_est4', 'logmcap', 'log_adv', 'ind_n']
ELIG = [c for c in fv3.PREDICTORS if c not in TECH]
METHODS = ['M0', 'M1', 'M2', 'M3', 'M4', 'M5']
DATES = sorted(B.date.unique())


def zs(s, d):
    g = s.groupby(d); return (s - g.transform('mean')) / g.transform('std')


SC, SEL, WTS, SEL4 = {}, [], [], []
for k in PNAME:
    Z = pd.read_pickle(f'{OUT}/Z_{k}.pkl'); X = B.loc[Z.index]
    cols = CAND[k] + ['logmcap']
    IC = ic_matrix(Z[ELIG], X.rk12_reg, X.date)
    ICt = ic_matrix(Z[ELIG], X.top5_reg, X.date); ICb = ic_matrix(Z[ELIG], X.bot20_reg, X.date)
    FMc = {tg: fm(Z, X[tg].astype(float), X.date, cols) for tg in TGT}
    xw = fv3.winsor(X.assign(xs=X.xs12_reg), ['xs'])['xs']
    FMc['xs'] = fm(Z, xw, X.date, cols)
    S = pd.DataFrame(index=X.index, columns=METHODS, dtype=float)
    S['M0'] = (Z[CAND[k]] - 0.5).mean(axis=1)
    for y, train, test in fv3.walk_forward_splits(DATES, 2015, 4):
        cut = max(train); te = X.date.isin(test)
        ic = IC[IC.index <= cut]
        tt = pd.Series({c: nwt(ic[c]) for c in ELIG}).dropna()
        sel = tt[tt.abs() >= 3].abs().sort_values(ascending=False).head(10).index
        if len(sel) == 0: sel = tt[tt.abs() >= 2].abs().sort_values(ascending=False).head(5).index
        sg = np.sign(tt[sel])
        S.loc[te, 'M1'] = ((Z.loc[te, sel] - 0.5) * sg).mean(axis=1) if len(sel) else 0.0
        SEL.append(dict(profilo=k, anno=y, n=len(sel), vars=' '.join(f"{c}{'+' if s > 0 else '-'}" for c, s in sg.items())))
        w = {tg: FMc[tg][FMc[tg].index <= cut].mean()[CAND[k]] for tg in TGT}
        S.loc[te, 'M2'] = (Z.loc[te, CAND[k]] - 0.5) @ w['rk12_reg']
        pt = (Z.loc[te, CAND[k]] - 0.5) @ w['top5_reg']; pb = (Z.loc[te, CAND[k]] - 0.5) @ w['bot20_reg']
        S.loc[te, 'M3'] = zs(pt, X.date[te]) - zs(pb, X.date[te])
        tb = pd.Series({c: nwt(ICt[ICt.index <= cut][c]) for c in ELIG}); tw = pd.Series({c: nwt(ICb[ICb.index <= cut][c]) for c in ELIG})
        sg4 = np.sign(tt)
        ok = (tt.abs() >= 2) & (sg4 * tb.reindex(tt.index) >= 0) & (sg4 * tw.reindex(tt.index) <= 0)
        sel4 = tt[ok].abs().sort_values(ascending=False).head(8).index
        S.loc[te, 'M4'] = ((Z.loc[te, sel4] - 0.5) * sg4[sel4]).mean(axis=1) if len(sel4) else S.loc[te, 'M0']
        SEL4.append(dict(profilo=k, anno=y, n=len(sel4), vars=' '.join(f"{c}{'+' if sg4[c] > 0 else '-'}" for c in sel4)))
        w['xs'] = FMc['xs'][FMc['xs'].index <= cut].mean()[CAND[k]]
        S.loc[te, 'M5'] = (Z.loc[te, CAND[k]] - 0.5) @ w['xs']
        for tg in TGT + ['xs']: WTS.append(dict(profilo=k, anno=y, target=tg, **w[tg].round(4).to_dict()))
    S = S[X.date.dt.year >= 2015]
    SC[k] = S
pd.to_pickle(SC, f'{OUT}/scores_oos.pkl')
pd.DataFrame(SEL).to_csv(f'{OUT}/wf_selezioni.csv', index=False)
pd.DataFrame(WTS).to_csv(f'{OUT}/wf_pesi.csv', index=False)
pd.DataFrame(SEL4).to_csv(f'{OUT}/wf_selezioni_M4.csv', index=False)
print(pd.DataFrame(SEL4).to_string())
