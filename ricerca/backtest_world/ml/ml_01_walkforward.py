# ml_01: walk-forward 2016-2026 (stima espansiva fino all'anno t-1 con 4 trimestri di distacco, prova sull'anno t).
# Modelli per ciascun target (rk12_reg, top5_reg, bot20_reg, crash50), stesse 67 variabili mondiali (ranghi per data x regione):
#   gbm  = LightGBM, 4 configurazioni prudenti x 6 numeri di alberi, scelta SOLO sulla validazione interna (ultime 4-8 date
#          della finestra di stima, con 4 trimestri di distacco dal resto), poi ristima su tutta la finestra
#   gbm1 = LightGBM con alberi a 1 taglio (modello additivo: non linearita' si', interazioni no)
#   lin  = Ridge (rango) / logistica L2 (binari), penalita' scelta sulla stessa validazione; NaN -> 0 (mediana)
# Uso: python ml_01_walkforward.py [GLOBAL|US]   (US = solo societa' americane, 81 variabili con i campi estesi; vedi ml_04)
import sys, os, time, json, numpy as np, pandas as pd, lightgbm as lgb
from sklearn.linear_model import Ridge, LogisticRegression
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc
MODE = sys.argv[1] if len(sys.argv) > 1 else 'GLOBAL'
M = mc.load()
if MODE == 'GLOBAL':
    VARS = mc.GLOBAL; ROWS = np.ones(len(M), bool); TAG = ''
elif MODE == 'US':
    VARS = mc.GLOBAL + mc.EXT; ROWS = (M.reg == 'USA').values; TAG = '_us'
elif MODE == 'USG':      # solo USA ma con le sole 67 variabili mondiali (confronto pulito per i campi estesi)
    VARS = mc.GLOBAL; ROWS = (M.reg == 'USA').values; TAG = '_usg'
X = mc.xcols(VARS)
MD = f'{mc.OUT}/models{TAG}'; os.makedirs(MD, exist_ok=True)
TARGETS = ['rk', 't5', 'b20', 'c50'] if MODE == 'GLOBAL' else ['rk', 't5', 'b20']
BASE = dict(learning_rate=0.05, subsample=0.7, subsample_freq=1, colsample_bytree=0.7, reg_lambda=10.0, max_bin=63,
            verbose=-1, n_jobs=int(os.environ.get('MLJOBS', 4)), random_state=7)
GRID = [dict(num_leaves=7, min_child_samples=500), dict(num_leaves=7, min_child_samples=2000),
        dict(num_leaves=31, min_child_samples=500), dict(num_leaves=31, min_child_samples=2000)]
CHK = [25, 50, 100, 200, 400, 600]
STUMP = dict(num_leaves=2, min_child_samples=500, learning_rate=0.1)
CHK1 = [100, 200, 400, 800, 1500]
ALPHAS = [1e1, 1e3, 1e4, 1e5, 1e6]
CS = [1e-4, 1e-3, 1e-2, 1e-1, 1.0]

dates = sorted(M.date.unique())
pred = pd.DataFrame(index=M.index[ROWS])
choices = []
log = open(f'{mc.OUT}/ml_01{TAG}.log', 'w')
def say(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.write(s + '\n'); log.flush()


def metric(k, p, D):
    y = D[mc.TGT[k]].values
    s = mc.ic_by_date(p, y, D.date.values) if k == 'rk' else mc.auc_by_date(p, y, D.date.values)
    return s.mean()


def make(k, params, n):
    P = {**BASE, **params, 'n_estimators': n}
    return lgb.LGBMRegressor(**P) if k == 'rk' else lgb.LGBMClassifier(**P)


def fit_predict(mdl, k, Xtr, ytr, Xte, n=None):
    mdl.fit(Xtr, ytr)
    if k == 'rk': return mdl, (lambda Z, n=n: mdl.predict(Z, num_iteration=n))
    return mdl, (lambda Z, n=n: mdl.predict_proba(Z, num_iteration=n)[:, 1])


MR = M[ROWS]
for y, inner, val, train, test in mc.splits(dates, 2016, 4):
    I = MR[MR.date.isin(inner)]; V = MR[MR.date.isin(val)]; T = MR[MR.date.isin(train)]; S = MR[MR.date.isin(test)]
    for k in TARGETS:
        tc = mc.TGT[k]
        Ii, Vv, Tt = I[I[tc].notna()], V[V[tc].notna()], T[T[tc].notna()]
        t0 = time.time()
        # --- gbm: griglia sulla validazione interna
        best = (-9, None, None); res = []
        for gi, g in enumerate(GRID):
            m = make(k, g, CHK[-1]); m.fit(Ii[X], Ii[tc])
            for n in CHK:
                p = m.predict(Vv[X], num_iteration=n) if k == 'rk' else m.predict_proba(Vv[X], num_iteration=n)[:, 1]
                v = metric(k, p, Vv); res.append((gi, n, v))
                if v > best[0]: best = (v, gi, n)
        vbest, gi, n = best
        m = make(k, GRID[gi], n); m.fit(Tt[X], Tt[tc])
        pred.loc[S.index, f'gbm_{k}'] = m.predict(S[X]) if k == 'rk' else m.predict_proba(S[X])[:, 1]
        m.booster_.save_model(f'{MD}/gbm_{k}_{y}.txt')
        # --- gbm1: additivo (alberi a un taglio)
        b1 = (-9, None)
        m1 = make(k, STUMP, CHK1[-1]); m1.fit(Ii[X], Ii[tc])
        for n1 in CHK1:
            p = m1.predict(Vv[X], num_iteration=n1) if k == 'rk' else m1.predict_proba(Vv[X], num_iteration=n1)[:, 1]
            v = metric(k, p, Vv)
            if v > b1[0]: b1 = (v, n1)
        m1 = make(k, STUMP, b1[1]); m1.fit(Tt[X], Tt[tc])
        pred.loc[S.index, f'gbm1_{k}'] = m1.predict(S[X]) if k == 'rk' else m1.predict_proba(S[X])[:, 1]
        m1.booster_.save_model(f'{MD}/gbm1_{k}_{y}.txt')
        # --- lineare
        bl = (-9, None)
        XI, XV = Ii[X].fillna(0).values, Vv[X].fillna(0).values
        for a in (ALPHAS if k == 'rk' else CS):
            lm = Ridge(alpha=a) if k == 'rk' else LogisticRegression(C=a, max_iter=300)
            lm.fit(XI, Ii[tc].values)
            p = lm.predict(XV) if k == 'rk' else lm.decision_function(XV)
            v = metric(k, p, Vv)
            if v > bl[0]: bl = (v, a)
        lm = Ridge(alpha=bl[1]) if k == 'rk' else LogisticRegression(C=bl[1], max_iter=300)
        lm.fit(Tt[X].fillna(0).values, Tt[tc].values)
        XS = S[X].fillna(0).values
        pred.loc[S.index, f'lin_{k}'] = lm.predict(XS) if k == 'rk' else lm.decision_function(XS)
        coef = pd.Series(lm.coef_.ravel(), index=VARS)
        choices.append(dict(anno=y, target=k, n_train=len(Tt), n_inner=len(Ii), n_val=len(Vv),
                            gbm_cfg=gi, gbm_leaves=GRID[gi]['num_leaves'], gbm_minleaf=GRID[gi]['min_child_samples'], gbm_trees=n, gbm_val=vbest,
                            gbm1_trees=b1[1], gbm1_val=b1[0], lin_pen=bl[1], lin_val=bl[0], lin_coef=json.dumps(coef.round(5).to_dict())))
        say(f'{y} {k}: train {len(Tt)} val {len(Vv)} | gbm cfg{gi} n{n} val {vbest:.4f} | gbm1 n{b1[1]} val {b1[0]:.4f} | lin {bl[1]:g} val {bl[0]:.4f} | {time.time()-t0:.0f}s')
pred.to_pickle(f'{mc.OUT}/wf_pred{TAG}.pkl')
pd.DataFrame(choices).to_csv(f'{mc.OUT}/wf_choices{TAG}.csv', index=False)
say('fatto', pred.shape)
