# ml_06: quanto si "gonfia" ciascun modello. Confronto fra il valore sulla validazione interna (usata per scegliere
# configurazione e numero di alberi) e il valore fuori campione nell'anno di prova; scelte degli iperparametri per anno.
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
C = pd.read_csv(f'{mc.OUT}/wf_choices.csv')
M = mc.load(); P = pd.read_pickle(f'{mc.OUT}/wf_pred.pkl'); M = M.loc[P.index].join(P); M = M[M.rk12_reg.notna()]
rows = []
for _, r in C.iterrows():
    S = M[M.date.dt.year == r.anno]
    if len(S) == 0: continue
    k = r.target; tc = mc.TGT[k]
    out = dict(anno=r.anno, target=k, cfg=f"{r.gbm_leaves}f/{r.gbm_minleaf}m/{r.gbm_trees}a", gbm1_alberi=r.gbm1_trees, lin_pen=r.lin_pen)
    for mdl in ['gbm', 'gbm1', 'lin']:
        s = mc.ic_by_date(S[f'{mdl}_{k}'].values, S[tc].values, S.date.values) if k == 'rk' else mc.auc_by_date(S[f'{mdl}_{k}'].values, S[tc].values, S.date.values)
        out[f'{mdl}_val'] = r[f'{mdl}_val']; out[f'{mdl}_oos'] = s.mean()
    rows.append(out)
T = pd.DataFrame(rows); T.to_csv(f'{mc.OUT}/sovradattamento.csv', index=False)
pd.set_option('display.width', 250); print(T.round(3).to_string())
G = T.groupby('target')[[c for c in T.columns if c.endswith('_val') or c.endswith('_oos')]].mean()
for m in ['gbm', 'gbm1', 'lin']: G[f'{m}_calo'] = G[f'{m}_val'] - G[f'{m}_oos']
print(G.round(4).to_string())
print(C.groupby('target')[['gbm_leaves', 'gbm_minleaf', 'gbm_trees']].agg(lambda s: s.value_counts().to_dict()).to_string())
