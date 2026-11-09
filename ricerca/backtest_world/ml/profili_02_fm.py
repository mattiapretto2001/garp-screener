# profili_02: regressione multipla (Fama-MacBeth) DENTRO ogni profilo sulle variabili candidate ex ante (+ capitalizzazione come controllo).
# Target: rango a 12 mesi nella regione, eccezionale (5% migliore della regione), disastro (20% peggiore). Coefficienti: variazione del
# target passando dal peggiore al migliore del profilo (rango 0 -> 1, segno a priori). t di Newey-West 4 ritardi. Periodo 2011-12 .. 2025-09.
from profili_common import *
from scipy.stats import norm
B = pd.read_pickle(f'{OUT}/base.pkl')
rows = []; VIF = {}
for k in PNAME:
    Z = pd.read_pickle(f'{OUT}/Z_{k}.pkl'); X = B.loc[Z.index]
    cols = CAND[k] + ['logmcap']
    C = Z[cols].corr(); VIF[k] = pd.Series(np.diag(np.linalg.inv(C.values)), index=cols).round(1)
    for tg in TGT:
        y = X[tg].astype(float).where(X[tg].notna())
        Cf = fm(Z, y, X.date, cols)
        Cg = {g: fm(Z[X.reg_rob == g], y[X.reg_rob == g], X.date[X.reg_rob == g], cols, min_n=25) for g in GROUPS}
        for c in cols:
            s = Cf[c]; m = s.mean()
            per = {p: s[(s.index >= a) & (s.index <= b)].mean() for p, (a, b) in fv3.PER3.items()}
            grp = {g: Cg[g][c].mean() if len(Cg[g]) >= 10 else np.nan for g in GROUPS}
            coh = sum(np.sign(v) == np.sign(m) for v in list(per.values()) + list(grp.values()) if pd.notna(v))
            rows.append(dict(profilo=k, target=tg, var=c, coef=m, t=nwt(s), **per, **grp, coer=coh, n_date=len(s)))
M = pd.DataFrame(rows)
M['p'] = 2 * norm.sf(M.t.abs()); mm = (M['var'] != 'logmcap')
o = M[mm].sort_values('p'); m = len(o)
M.loc[o.index, 'holm'] = (o.p * (m - np.arange(m))).cummax().clip(upper=1).values < 0.05
M.to_csv(f'{OUT}/fm_profili.csv', index=False)
print('prove (escluso controllo)', m, '| |t|>=2:', (M[mm].t.abs() >= 2).sum(), '| |t|>=3:', (M[mm].t.abs() >= 3).sum(), '| Holm:', int(M.holm.fillna(False).sum()))
print({k: v.max() for k, v in VIF.items()})
pd.set_option('display.width', 250)
for k in PNAME:
    W = M[M.profilo == k].pivot_table(index='var', columns='target', values=['coef', 't'], sort=False)
    coh = M[M.profilo == k].pivot_table(index='var', columns='target', values='coer', sort=False)
    W = pd.concat([W['coef'].add_prefix('b_'), W['t'].add_prefix('t_'), coh.add_prefix('c_')], axis=1)
    print(f'\n== {k}'); print(W.round(3).sort_values('t_rk12_reg', ascending=False).to_string())
