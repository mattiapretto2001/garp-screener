# univariata_01: IC di rango (target a) e AUC-0,5 (target b, c) per OGNI variabile predittiva della matrice features_v3.
# Statistica per data (ranghi dentro data x regione), media, t di Newey-West (4 ritardi), segno per periodo,
# segno per gruppo di regioni (target ricalcolati dentro il gruppo), controllo walk-forward del segno, versione intra-settore,
# correzione per prove multiple (Holm, Benjamini-Hochberg).
import numpy as np, pandas as pd, pickle, time
from scipy import stats
from univariata_common import *
t0 = time.time()
F = load_dev(); P = fv3.PREDICTORS
dates = np.sort(F.date.unique()); DI = {d: i for i, d in enumerate(dates)}
F['di'] = F.date.map(DI).astype(int)
print('righe', len(F), 'date', len(dates), dates[0], dates[-1])

# ---------- 1) pooled: ranghi dentro data x regione (4 regioni dei target), statistica per data
R = pct_rank(F, P, ['date', 'reg'])
SER = {}                                            # (scheme, var, tgt) -> Series per data (o per data x gruppo)
gd = F.di.values
for v in P:
    x = R[v].values.astype(float)
    for tk, tc in TGT.items():
        y = F[tc].values.astype(float)
        s = group_stat(x, y, gd, 'ic' if tk == 'rk' else 'auc')
        SER[('pool', v, tk)] = pd.Series(s, index=dates)
print('pooled fatto', round(time.time() - t0))

# ---------- 2) gruppi di regioni: target ricalcolati DENTRO il gruppo (es. USA grandi contro USA grandi)
gk = ['date', 'reg_rob']
g = F.groupby(gk, observed=True).fwd12_eur
rkg = (g.rank(method='average') - 0.5) / g.transform('count')
TG = {'rk': rkg, 'top5': (rkg >= 0.95).astype(float), 'bot20': (rkg <= 0.20).astype(float), 'crash': F.crash50.astype(float)}
RG = pct_rank(F, P, gk)
REGS = list(F.reg_rob.cat.categories) if hasattr(F.reg_rob, 'cat') else sorted(F.reg_rob.unique())
REGS = [r for r in REGS if r in F.reg_rob.unique()]
RI = {r: i for i, r in enumerate(REGS)}
code = F.di.values * len(REGS) + F.reg_rob.astype(str).map(RI).values
for v in P:
    x = RG[v].values.astype(float)
    for tk in TGT:
        s = group_stat(x, TG[tk].values, code, 'ic' if tk == 'rk' else 'auc')
        s = np.concatenate([s, np.full(len(dates) * len(REGS) - len(s), np.nan)]).reshape(len(dates), len(REGS))
        for r in REGS:
            SER[('reg', v, tk, r)] = pd.Series(s[:, RI[r]], index=dates)
print('regioni fatto', round(time.time() - t0))

# ---------- 3) intra-settore: rango della variabile dentro data x regione x settore (gruppi >=10 societa')
gs = ['date', 'reg', 'sector_n']
RS = pct_rank(F, P, gs)
cnt = F.groupby(gs, observed=True)[P].transform('count')
RS = RS.where(cnt >= 10)
for v in P:
    x = RS[v].values.astype(float)
    for tk in TGT_MAIN:
        SER[('sect', v, tk)] = pd.Series(group_stat(x, F[TGT[tk]].values.astype(float), gd, 'ic' if tk == 'rk' else 'auc'), index=dates)
print('settore fatto', round(time.time() - t0))
# ---------- 3b) neutrale alla volatilita': rango dentro data x regione x quintile di volatilita' a 1 anno.
# Serve a capire se una variabile riconosce gli 'eccezionali' oltre al semplice fatto di essere un titolo molto mobile.
F['volq'] = np.ceil(pct_rank(F, ['vol1y'], ['date', 'reg'])['vol1y'] * 5).clip(1, 5)
gv = ['date', 'reg', 'volq']
RV = pct_rank(F, P, gv)
cnt = F.groupby(gv, observed=True)[P].transform('count')
RV = RV.where(cnt >= 10)
for v in P:
    x = RV[v].values.astype(float)
    for tk in TGT_MAIN:
        SER[('vol', v, tk)] = pd.Series(group_stat(x, F[TGT[tk]].values.astype(float), gd, 'ic' if tk == 'rk' else 'auc'), index=dates)
print('vol-neutrale fatto', round(time.time() - t0))
pickle.dump(SER, open(f'{OUT}/ic_series.pkl', 'wb'))

# ---------- 4) sintesi
per_of = F.groupby('date').per3.first().reindex(dates).astype(str).values
WF = list(fv3.walk_forward_splits(pd.Series(dates), 2016, 4))


def summ(s):
    s = s.dropna()
    return s.mean(), fv3.nw_t(s, 4), len(s), (s > 0).mean()


rows = []
for v in P:
    for tk in TGT:
        s = SER[('pool', v, tk)]
        m, t, n, pos = summ(s)
        row = dict(var=v, fam=[f for f, l in fv3.FAMILIES.items() if v in l][0], tgt=tk, dir_prior=fv3.DIRECTION.get(v, 0),
                   mean=m, t=t, n_dates=n, frac_pos=pos, cov=F[v].notna().mean())
        for p in PERS:
            row[f'per_{p}'] = s[per_of == p].mean()
        for r in REGS:
            sr = SER[('reg', v, tk, r)].dropna()
            row[f'reg_{r}'] = sr.mean() if len(sr) >= 12 else np.nan
            row[f't_{r}'] = fv3.nw_t(sr, 4) if len(sr) >= 12 else np.nan
        # walk-forward: segno scelto sui dati di addestramento (fino a t-1 meno 4 trimestri), misurato sull'anno t
        oos = []
        for y, tr, te in WF:
            st = s.reindex(pd.to_datetime(tr)).dropna(); se = s.reindex(pd.to_datetime(te)).dropna()
            if len(st) >= 8 and len(se): oos.append(np.sign(st.mean()) * se.mean())
        row['wf_oos'] = np.mean(oos) if oos else np.nan; row['wf_hit'] = np.mean(np.array(oos) > 0) if oos else np.nan
        row['wf_n'] = len(oos)
        if tk in TGT_MAIN:
            ms, tsec, _, _ = summ(SER[('sect', v, tk)]); row['sect_mean'] = ms; row['sect_t'] = tsec
            mv, tv, _, _ = summ(SER[('vol', v, tk)]); row['vol_mean'] = mv; row['vol_t'] = tv
        rows.append(row)
S = pd.DataFrame(rows)
S['p'] = 2 * stats.t.sf(S.t.abs(), S.n_dates - 1)
S['sgn'] = np.sign(S['mean'])
S['n_per_same'] = sum((np.sign(S[f'per_{p}']) == S.sgn).astype(int) for p in PERS)
S['n_reg4_same'] = sum((np.sign(S[f'reg_{r}']) == S.sgn).astype(int) for r in REG4)
S['n_reg4_avail'] = sum(S[f'reg_{r}'].notna().astype(int) for r in REG4)
main = S.tgt.isin(TGT_MAIN)
S.loc[main, 'p_holm'] = holm(S.loc[main, 'p']); S.loc[main, 'q_bh'] = bh(S.loc[main, 'p'])
cons = (S.n_per_same == 3) & (S.n_reg4_same >= 3)
S['verdetto'] = np.where((S.t.abs() >= 2.5) & cons, 'solida', np.where(S.t.abs() >= 2.0, 'fragile', 'debole'))
S.loc[(S.t.abs() >= 2.5) & ~cons, 'verdetto'] = 'fragile'
# segno "buono" per l'investitore: + = alza il rango / alza P(top5) / ABBASSA P(bot20) / abbassa P(crash)
S['good'] = np.where(S.tgt.isin(['bot20', 'crash']), -S['mean'], S['mean'])
S.to_csv(f'{OUT}/ic_summary.csv', index=False)
print(S[main].groupby('tgt').verdetto.value_counts().unstack())
print('Holm p<0.05:', S[main].groupby('tgt').apply(lambda d: (d.p_holm < 0.05).sum()).to_dict())
print('BH q<0.05:', S[main].groupby('tgt').apply(lambda d: (d.q_bh < 0.05).sum()).to_dict())
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
for tk in TGT_MAIN:
    d = S[S.tgt == tk].sort_values('t', key=abs, ascending=False)
    print('\n====', tk)
    print(d[['var', 'fam', 'mean', 't', 'frac_pos'] + [f'per_{p}' for p in PERS] + [f'reg_{r}' for r in REG4] +
            ['wf_oos', 'wf_hit', 'sect_t', 'vol_t', 'p_holm', 'verdetto']].round(3).head(45).to_string(index=False))
print('fine', round(time.time() - t0))
