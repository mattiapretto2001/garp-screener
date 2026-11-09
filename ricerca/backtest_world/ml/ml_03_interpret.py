# ml_03: interpretazione dei modelli gbm walk-forward, SOLO sugli anni di prova (fuori campione):
#  - SHAP (TreeSHAP di LightGBM): quota media di |SHAP| per variabile e famiglia, segno dell'effetto, stabilita' fra anni
#  - importanza per permutazione: calo dell'IC/AUC fuori campione mescolando una variabile (o una famiglia) dentro ogni data
#  - interazioni: valori di interazione SHAP (campione di 1.500 righe per anno), coppie piu' forti; celle 3x3 per coppie a priori
#  - forme degli effetti dal modello additivo (gbm1): SHAP medio per decile della variabile
import sys, os, warnings, numpy as np, pandas as pd, lightgbm as lgb, shap
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
TAG = sys.argv[1] if len(sys.argv) > 1 else ''
M = mc.load()
VARS = mc.GLOBAL + (mc.EXT if TAG == '_us' else [])
X = mc.xcols(VARS)
if TAG == '_us': M = M[M.reg == 'USA']
TG = ['rk', 't5', 'b20', 'c50'] if TAG == '' else ['rk', 't5', 'b20']
MD = f'{mc.OUT}/models{TAG}'
YEARS = range(2016, 2027)
PAIRS = [('revq', 'ev_sales'), ('revq', 'hi52'), ('logmcap', 'mom12_1'), ('rev_cagr', 'mom12_1'), ('revq', 'roe'), ('vol1y', 'logmcap'),
         ('fcf_m', 'revq'), ('rev_cagr', 'ev_sales')]
rng = np.random.default_rng(11)
imp, sgn, perm, inter, cells, shapes = [], [], [], [], [], []
for k in TG:
    tc = mc.TGT[k]
    for y in YEARS:
        fn = f'{MD}/gbm_{k}_{y}.txt'
        if not os.path.exists(fn): continue
        b = lgb.Booster(model_file=fn); b1 = lgb.Booster(model_file=f'{MD}/gbm1_{k}_{y}.txt')
        S = M[M.date.dt.year == y]
        XS = S[X]
        C = b.predict(XS, pred_contrib=True)[:, :-1]
        a = np.abs(C).mean(0); imp.append(pd.Series(a / a.sum(), index=VARS).rename((k, y)))
        # segno: correlazione di rango fra valore (con segno a priori) e contributo SHAP
        sg = {v: pd.Series(XS.iloc[:, i].values).corr(pd.Series(C[:, i]), method='spearman') for i, v in enumerate(VARS)}
        sgn.append(pd.Series(sg).rename((k, y)))
        # forme dal modello additivo
        C1 = b1.predict(XS, pred_contrib=True)[:, :-1]
        for i, v in enumerate(VARS):
            z = XS.iloc[:, i].values
            q = np.where(np.isnan(z), -1, np.floor(np.clip(z / np.sqrt(12) + 0.5, 0, 0.9999) * 10)).astype(int)
            prof = pd.Series(C1[:, i]).groupby(q).mean()
            shapes.append(dict(target=k, anno=y, var=v, **{f'd{j}': prof.get(j, np.nan) for j in range(-1, 10)}))
        # permutazione (fuori campione), con etichette disponibili
        L = S[S[tc].notna()]
        if len(L):
            XL = L[X].copy()
            def score(Z):
                p = b.predict(Z)
                s = mc.ic_by_date(p, L[tc].values, L.date.values) if k == 'rk' else mc.auc_by_date(p, L[tc].values, L.date.values)
                return s
            base = score(XL)
            groups = {v: [f'z_{v}'] for v in VARS}
            for f, vs in fv3.FAMILIES.items():
                vv = [f'z_{v}' for v in vs if v in VARS]
                if vv: groups['FAM:' + f] = vv
            dix = [np.where(L.date.values == d)[0] for d in sorted(L.date.unique())]
            for gname, cols in groups.items():
                Z = XL.copy(); arr = Z[cols].to_numpy(copy=True)
                for ix in dix: arr[ix] = arr[rng.permutation(ix)]
                Z[cols] = arr
                s = score(Z)
                perm.append(dict(target=k, anno=y, gruppo=gname, **{str(d.date()): base[d] - s[d] for d in base.index}))
        # interazioni SHAP su un campione
        smp = XS.sample(min(1500, len(XS)), random_state=y)
        IV = shap.TreeExplainer(b).shap_interaction_values(smp.values)
        A = np.abs(IV).mean(0); tot = A.sum()
        iu = np.triu_indices(len(VARS), 1)
        inter.append(pd.Series(2 * A[iu] / tot, index=[f'{VARS[i]} x {VARS[j]}' for i, j in zip(*iu)]).rename((k, y)))
        inter.append(pd.Series([np.trace(A) / tot], index=['__diagonale']).rename((k, y, 'diag')))
        for va, vb in PAIRS:
            ia, ib = VARS.index(va), VARS.index(vb)
            za, zb = smp[f'z_{va}'].values, smp[f'z_{vb}'].values
            ta = np.where(np.isnan(za), -1, np.digitize(za, [-0.577, 0.577])); tb = np.where(np.isnan(zb), -1, np.digitize(zb, [-0.577, 0.577]))
            val = 2 * IV[:, ia, ib]
            for i in range(3):
                for j in range(3):
                    m = (ta == i) & (tb == j)
                    cells.append(dict(target=k, anno=y, coppia=f'{va} x {vb}', ta=i, tb=j, n=m.sum(), inter=val[m].mean() if m.any() else np.nan))
        print(k, y, 'ok', flush=True)
IMP = pd.concat(imp, axis=1); IMP.to_pickle(f'{mc.OUT}/int_imp{TAG}.pkl')
SGN = pd.concat(sgn, axis=1); SGN.to_pickle(f'{mc.OUT}/int_sgn{TAG}.pkl')
PERM = pd.DataFrame(perm); PERM.to_pickle(f'{mc.OUT}/int_perm{TAG}.pkl')
INT = pd.concat([s for s in inter if len(s.name) == 2], axis=1); INT.to_pickle(f'{mc.OUT}/int_pairs{TAG}.pkl')
DIAG = pd.concat([s for s in inter if len(s.name) == 3], axis=1); DIAG.to_pickle(f'{mc.OUT}/int_diag{TAG}.pkl')
pd.DataFrame(cells).to_pickle(f'{mc.OUT}/int_cells{TAG}.pkl')
pd.DataFrame(shapes).to_pickle(f'{mc.OUT}/int_shapes{TAG}.pkl')
print('fatto')
