# regressioni_02: walk-forward elastic net / LASSO / OLS / composito trasparente FM.
# Addestra su date <= (inizio anno t - 4 trimestri di distacco), predice le date dell'anno t, t = 2015..2026.
# alpha scelto con convalida incrociata per ANNI dentro la sola finestra di addestramento (GroupKFold).
import sys, os, time, warnings, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
from sklearn.linear_model import ElasticNetCV, LinearRegression
from sklearn.model_selection import GroupKFold
warnings.filterwarnings('ignore')
T0 = time.time(); OUT = rc.HERE + '/reg_out'
M = rc.load().reset_index(drop=True)
P = fv3.PREDICTORS; ZP = ['z_' + c for c in P]; G = rc.GLOBAL; ZG = ['z_' + c for c in G]
M['y_rk'] = (M.rk12_reg - 0.5) * rc.S12
M['y_t5'] = M.top5_reg.astype(float); M['y_b20'] = M.bot20_reg.astype(float)
M.loc[M.fwd12_eur.isna(), ['y_t5', 'y_b20']] = np.nan
X = M[ZP].fillna(0).values.astype(np.float64)
XG = M[ZG].fillna(0).values.astype(np.float64)
dates = M.date.values
preds = {k: np.full(len(M), np.nan) for k in ['enet_rk', 'lasso_rk', 'enet_t5', 'enet_b20', 'ols37_rk', 'fmcomp']}
coefs = []
for yr, train, test in fv3.walk_forward_splits(M.date, first_test_year=2015, embargo_q=4):
    tr = np.isin(dates, np.array(train, dtype='datetime64[ns]'))
    te = np.isin(dates, np.array(test, dtype='datetime64[ns]'))
    yrs = pd.DatetimeIndex(dates[tr]).year.values
    ng = len(set(yrs)); cv = list(GroupKFold(n_splits=min(5, ng)).split(X[tr], groups=yrs))
    for name, ycol, l1 in [('enet_rk', 'y_rk', 0.5), ('lasso_rk', 'y_rk', 1.0), ('enet_t5', 'y_t5', 0.5), ('enet_b20', 'y_b20', 0.5)]:
        y = M[ycol].values; ok = tr & ~np.isnan(y)
        cvk = list(GroupKFold(n_splits=min(5, ng)).split(X[ok], groups=pd.DatetimeIndex(dates[ok]).year.values))
        m = ElasticNetCV(l1_ratio=l1, alphas=25, cv=cvk, n_jobs=4, tol=1e-3, max_iter=3000).fit(X[ok], y[ok])
        preds[name][te] = m.predict(X[te])
        coefs.append(pd.Series(m.coef_, index=P).rename((yr, name, m.alpha_)))
    ok = tr & ~np.isnan(M.y_rk.values)
    lr = LinearRegression().fit(XG[ok], M.y_rk.values[ok]); preds['ols37_rk'][te] = lr.predict(XG[te])
    coefs.append(pd.Series(dict(zip(G, lr.coef_))).reindex(P).rename((yr, 'ols37_rk', 0)))
    # composito trasparente: FM sulle 37 nella finestra; variabili con |t|>=2 -> media dei z col segno stimato
    S = M.loc[ok, ['date'] + ZG + ['y_rk']]
    C = rc.fm(S, ZG, 'y_rk'); sm = rc.summarize(C)
    sel = sm[sm.t.abs() >= 2]
    w = np.sign(sel.coef.values)
    idx = [ZG.index(c) for c in sel.index]
    preds['fmcomp'][te] = (XG[te][:, idx] * w).mean(1) if len(idx) else 0
    coefs.append(pd.Series(dict(zip([c[2:] for c in sel.index], w))).reindex(P).fillna(0).rename((yr, 'fmcomp', len(idx))))
    print(yr, 'train date', len(train), 'righe', tr.sum(), 'test', te.sum(), 'fmcomp:', [c[2:] for c in sel.index], round(time.time() - T0), flush=True)
CO = pd.DataFrame(coefs)
CO.index = pd.MultiIndex.from_tuples(CO.index, names=['anno', 'modello', 'alpha_o_n'])
CO.to_csv(f'{OUT}/enet_coef.csv')
PR = pd.DataFrame(preds); PR['t'] = M.t; PR['date'] = M.date
PR.to_pickle(f'{OUT}/enet_pred.pkl')
print('fine', round(time.time() - T0))
