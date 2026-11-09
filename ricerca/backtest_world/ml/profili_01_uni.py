# profili_01: per ogni profilo, ogni variabile (81) e ogni target (rango, eccezionale, disastro): correlazione per data DENTRO il profilo,
# t di Newey-West (4 ritardi), segno per periodo e per gruppo di regioni. Solo date 2011-12 .. 2025-09 (esito a 12 mesi noto).
from profili_common import *
from scipy.stats import norm
B = pd.read_pickle(f'{OUT}/base.pkl')


rows = []
for k in PNAME:
    Z = pd.read_pickle(f'{OUT}/Z_{k}.pkl'); X = B.loc[Z.index]
    for tg in TGT:
        IC = ic_matrix(Z, X[tg], X.date)
        ICg = {g: ic_matrix(Z[X.reg_rob == g], X.loc[X.reg_rob == g, tg], X.date[X.reg_rob == g], min_n=20) for g in GROUPS}
        for c in fv3.PREDICTORS:
            s = IC[c].dropna(); m = s.mean(); t = nwt(s)
            per = {p: s[(s.index >= a) & (s.index <= b)].mean() for p, (a, b) in fv3.PER3.items()}
            grp = {g: ICg[g][c].dropna().mean() if len(ICg[g]) >= 10 else np.nan for g in GROUPS}
            coh = sum(np.sign(v) == np.sign(m) for v in list(per.values()) + list(grp.values()) if pd.notna(v))
            rows.append(dict(profilo=k, target=tg, var=c, cand=c in CAND[k], ic=m, t=t, **per, **grp, coer=coh, n_date=len(s)))
U = pd.DataFrame(rows)
U['p'] = 2 * norm.sf(U.t.abs())
U = U.sort_values('p'); m = len(U)
U['holm'] = (U.p * (m - np.arange(m))).cummax().clip(upper=1).values < 0.05     # Holm su tutte le 1215 prove
U = U.sort_index()
U['solida'] = (U.t.abs() >= 3) & (U.coer >= 6)
U.to_csv(f'{OUT}/uni_ic.csv', index=False)
print('prove', m, '| |t|>=2:', (U.t.abs() >= 2).sum(), '| |t|>=3:', (U.t.abs() >= 3).sum(), '| Holm:', U.holm.sum(), '| solide (t>=3, coer>=6/7):', U.solida.sum())
pd.set_option('display.width', 250)
for k in PNAME:
    for tg in TGT:
        x = U[(U.profilo == k) & (U.target == tg)].copy()
        x = x.reindex(x.t.abs().sort_values(ascending=False).index).head(12)
        print(f'\n== {k} {tg}')
        print(x[['var', 'cand', 'ic', 't', '2012-16', '2017-21', '2022-26'] + GROUPS + ['coer', 'holm']].round(3).to_string(index=False))
