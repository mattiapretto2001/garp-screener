# avv_uni_03 (verifica avversariale): il controllo walk-forward del report sceglie il SEGNO sul passato ma l'insieme delle
# variabili "solide" e' scelto su TUTTO il 2012-2026 (anni di test compresi). Qui la selezione stessa e' rifatta ogni anno
# solo sul passato (con 4 trimestri di distacco) e misurata sull'anno nuovo. Confronto con: insieme scelto col senno di poi,
# e punteggio con le sole direzioni a priori (fv3.DIRECTION, nessuna scelta sui dati).
import numpy as np, pandas as pd
from univariata_common import *
F = load_dev(); P = fv3.PREDICTORS
SER = pd.read_pickle(f'{OUT}/ic_series.pkl')
S0 = pd.read_csv(f'{OUT}/ic_summary.csv')
dates = np.sort(F.date.unique())
WF = list(fv3.walk_forward_splits(pd.Series(dates), 2016, 4))
print('WF% medio dichiarato, solide su rk:', round(S0[(S0.tgt=='rk')&(S0.verdetto=='solida')].wf_hit.mean(),3),
      ' deboli:', round(S0[(S0.tgt=='rk')&(S0.verdetto=='debole')].wf_hit.mean(),3))
solid_full = S0[(S0.tgt == 'rk') & (S0.verdetto == 'solida')]['var'].tolist()
sgn_full = S0[S0.tgt == 'rk'].set_index('var')['mean'].apply(np.sign)
R = pct_rank(F, P, ['date', 'reg'])
y = F.rk12_reg.values.astype(float); yb = F.bot20_reg.values.astype(float); yt = F.top5_reg.values.astype(float)

def comp_ic(vars_, signs, test_dates):
    """IC per data del punteggio = media dei ranghi con segno delle variabili scelte (mancanti = 0,5)"""
    if not vars_: return [], [], []
    Z = np.column_stack([(R[v].values if signs[v] > 0 else 1 - R[v].values) for v in vars_]).astype(float)
    Z = np.where(np.isnan(Z), 0.5, Z).mean(axis=1)
    ics, aucb, auct = [], [], []
    for d in test_dates:
        m = (F.date == d).values
        z = pd.Series(Z[m]).groupby(F.reg.values[m]).rank(pct=True).values
        ics.append(np.corrcoef(z, y[m])[0, 1])
        aucb.append(z[yb[m] == 1].mean() - z[yb[m] == 0].mean()); auct.append(z[yt[m] == 1].mean() - z[yt[m] == 0].mean())
    return ics, aucb, auct

rows = []; hits_tr, hits_full = [], []
for yr, tr, te in WF:
    tr = pd.to_datetime(tr); te = pd.to_datetime(te)
    half = tr[len(tr) // 2]
    sel, sg = [], {}
    for v in P:
        s = SER[('pool', v, 'rk')].reindex(tr).dropna()
        if len(s) < 8: continue
        t = fv3.nw_t(s, 4); m = s.mean(); sg[v] = np.sign(m)
        h1, h2 = s[s.index < half].mean(), s[s.index >= half].mean()
        nreg = sum(np.sign(SER[('reg', v, 'rk', r)].reindex(tr).dropna().mean()) == np.sign(m) for r in REG4)
        if abs(t) >= 2.5 and np.sign(h1) == np.sign(h2) == np.sign(m) and nreg >= 3: sel.append(v)
    for v in sel:
        se = SER[('pool', v, 'rk')].reindex(te).dropna()
        if len(se): hits_tr.append(sg[v] * se.mean() > 0)
    for v in solid_full:
        se = SER[('pool', v, 'rk')].reindex(te).dropna()
        s = SER[('pool', v, 'rk')].reindex(tr).dropna()
        if len(se) and len(s) >= 8: hits_full.append(np.sign(s.mean()) * se.mean() > 0)
    a_tr = comp_ic(sel, sg, te)
    a_full = comp_ic(solid_full, sgn_full.to_dict(), te)
    pri = [v for v in P if fv3.DIRECTION.get(v, 0) != 0]
    a_pri = comp_ic(pri, {v: fv3.DIRECTION[v] for v in pri}, te)
    a_dsh = comp_ic(['dsh3'], {'dsh3': -1}, te)
    rows.append(dict(anno=yr, n_train=len(tr), n_sel=len(sel), sel=','.join(sel),
                     ic_sel=np.mean(a_tr[0]) if sel else np.nan, ic_senno=np.mean(a_full[0]), ic_priori=np.mean(a_pri[0]), ic_dsh3=np.mean(a_dsh[0]),
                     b20_sel=np.mean(a_tr[1]) if sel else np.nan, b20_senno=np.mean(a_full[1]), b20_priori=np.mean(a_pri[1]),
                     t5_sel=np.mean(a_tr[2]) if sel else np.nan, t5_senno=np.mean(a_full[2]), t5_priori=np.mean(a_pri[2])))
W = pd.DataFrame(rows)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 120)
print(W.drop(columns='sel').round(3).to_string(index=False))
for r in W.itertuples(): print(r.anno, r.sel)
print('\nquota segno giusto fuori campione: selezione sul passato', round(np.mean(hits_tr), 3), 'n', len(hits_tr),
      '| insieme col senno di poi', round(np.mean(hits_full), 3), 'n', len(hits_full))
for c in ['ic_sel', 'ic_senno', 'ic_priori', 'ic_dsh3', 'b20_sel', 'b20_senno', 'b20_priori', 't5_sel', 't5_senno', 't5_priori']:
    z = W[c].dropna(); print(f'{c:10s} media {z.mean():+.4f}  anni>0 {int((z>0).sum())}/{len(z)}  t {z.mean()/(z.std(ddof=1)/np.sqrt(len(z))):+.2f}')
W.to_csv(f'{OUT}/avv_wf_annidato.csv', index=False)
