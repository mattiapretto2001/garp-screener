# ml_04: solo societa' americane. Valore dei campi estesi (margine lordo, R&S, spese generali, sorprese, copertura analisti, eta')
# per il modello non lineare e per quello lineare: stessi anni di prova, stesse righe, con (US, 81 variabili) e senza (USG, 67).
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ml_common as mc, fv3
M = mc.load()
A = pd.read_pickle(f'{mc.OUT}/wf_pred_us.pkl').add_suffix('_ext'); B = pd.read_pickle(f'{mc.OUT}/wf_pred_usg.pkl')
G = pd.read_pickle(f'{mc.OUT}/wf_pred.pkl').add_suffix('_mondo')
D = M.loc[A.index].join(A).join(B).join(G)
D = D[D.gbm_rk_ext.notna() & D.rk12_reg.notna()]
rows = []; S = {}
for k in ['rk', 't5', 'b20']:
    tc = mc.TGT[k]; base = 0 if k == 'rk' else 0.5
    for mdl in ['gbm', 'gbm1', 'lin']:
        for v in ['_ext', '', '_mondo']:
            c = f'{mdl}_{k}{v}'
            s = mc.ic_by_date(D[c].values, D[tc].values, D.date.values) if k == 'rk' else mc.auc_by_date(D[c].values, D[tc].values, D.date.values)
            S[(k, mdl, v)] = s
            r = dict(target=k, modello=mdl, variabili={'_ext': '81 (con estesi), stima USA', '': '67 mondiali, stima USA', '_mondo': '67, stima mondo'}[v],
                     media=s.mean(), t=fv3.nw_t(s - base, 4))
            for p in mc.PERS:
                sp = s[[mc.perlab(d) == p for d in s.index]]; r[p] = sp.mean()
            for g in ['USA grandi', 'USA piccole/medie']:
                Dg = D[D.reg_rob == g]
                sg = mc.ic_by_date(Dg[c].values, Dg[tc].values, Dg.date.values) if k == 'rk' else mc.auc_by_date(Dg[c].values, Dg[tc].values, Dg.date.values)
                r[g] = sg.mean()
            rows.append(r)
T = pd.DataFrame(rows); T.to_csv(f'{mc.OUT}/usa_estesi.csv', index=False)
pd.set_option('display.width', 250); print(T.round(3).to_string())
for k in ['rk', 't5', 'b20']:
    for a, b in [(('gbm', '_ext'), ('gbm', '')), (('lin', '_ext'), ('lin', '')), (('gbm', '_ext'), ('lin', '_ext')), (('gbm', ''), ('lin', '')),
                 (('gbm', ''), ('gbm', '_mondo'))]:
        d = (S[(k, *a)] - S[(k, *b)]).dropna()
        print(k, a, 'vs', b, f'diff {d.mean():+.4f} t {fv3.nw_t(d, 4):.2f}', 'per periodo', [round(d[[mc.perlab(x) == p for x in d.index]].mean(), 4) for p in mc.PERS])
