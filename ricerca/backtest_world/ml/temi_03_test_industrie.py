# temi_03: test (a). Le industrie segnalate "emergenti" alla data t battono le altre nei 12 mesi dopo?
from temi_common import *
V = pd.read_pickle(f'{OUT}/ind_flags.pkl')
RULES = ['A', 'Aplus', 'B', 'Bplus', 'W', 'MOM', 'CALDE']
CI = pd.read_pickle(f'{OUT}/comp_ind.pkl')
Fc = fv3.load(cols=['t', 'date', 'reg_rob', 'fwd12_eur', 'xs12_reg', 'top5_reg', 'bot20_reg', 'crash50', 'r_eur', 'mcap_usd'])
C = CI.merge(Fc, on=['t', 'date'], how='left')
C = C.merge(V[['ind', 'date'] + RULES], on=['ind', 'date'], how='left')
C['elig'] = C[RULES[0]].notna()          # industria valida (>=8) e idonea alla data
for r in RULES: C[r] = C[r].fillna(False).astype(bool)
E = C[C.elig].copy()
Y = E[E.fwd12_eur.notna()]
dates = sorted(Y.date.unique())
rows, per_rows, reg_rows = [], [], []
# eccesso dentro il gruppo regionale di robustezza, rispetto alle societa' idonee dello stesso gruppo alla data
Y = Y.assign(xs_rob=Y.fwd12_eur - Y.groupby(['date', 'reg_rob']).fwd12_eur.transform('mean'))
base = Y.groupby('date').agg(b_xs=('xs12_reg', 'mean'), b_top5=('top5_reg', 'mean'), b_bot20=('bot20_reg', 'mean'), b_crash=('crash50', 'mean'))
VI = V[V.y_xs.notna()].copy(); VI['y_rel'] = VI.y_xs - VI.groupby('date').y_xs.transform('mean')
for r in RULES:
    S = Y[Y[r]]
    g = S.groupby('date').agg(ecc=('xs12_reg', 'mean'), top5=('top5_reg', 'mean'), bot20=('bot20_reg', 'mean'), crash=('crash50', 'mean'), n=('t', 'size'))
    g = g.join(base, how='right'); g['sp'] = g.ecc - g.b_xs
    sp = g.sp.dropna()
    # livello industria (ogni industria pesa uguale)
    fl = VI[VI[r]]; isp = fl.groupby('date').y_rel.mean()
    hit = (fl.y_rel > 0).mean(); fail = (fl.y_rel < -0.10).mean(); fail_nf = (VI[~VI[r]].y_rel < -0.10).mean()
    rows.append({'regola': r, 'date_con_segnali': len(sp), 'societa_medie': round(g.n.mean(), 0), 'ecc_soc_pp': 100 * sp.mean(), 't_soc': nw_t(sp),
                 'ecc_ind_pp': 100 * isp.mean(), 't_ind': nw_t(isp), 'quota_date_pos': (sp > 0).mean(),
                 'ind_battono_altre': hit, 'ind_fallite(<-10pp)': fail, 'fallite_non_segnalate': fail_nf,
                 'top5': g.top5.mean(), 'top5_base': g.b_top5.mean(), 'bot20': g.bot20.mean(), 'bot20_base': g.b_bot20.mean(),
                 'crollo50': g.crash.mean(), 'crollo50_base': g.b_crash.mean()})
    for p in PER3:
        s = sp[[per3_of(d) == p for d in sp.index]]
        per_rows.append({'regola': r, 'periodo': p, 'ecc_pp': 100 * s.mean(), 't': nw_t(s), 'n_date': len(s)})
    for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia']:
        s = S[S.reg_rob == rg].groupby('date').xs_rob.mean()
        reg_rows.append({'regola': r, 'gruppo': rg, 'ecc_pp': 100 * s.mean(), 't': nw_t(s), 'soc_medie': S[S.reg_rob == rg].groupby('date').size().mean()})
R = pd.DataFrame(rows); R['p_holm'] = holm([tp(t) for t in R.t_soc])
pd.set_option('display.width', 250)
print(R.round(3).to_string())
P = pd.DataFrame(per_rows).pivot(index='regola', columns='periodo', values=['ecc_pp', 't']).round(2); print(P.to_string())
G = pd.DataFrame(reg_rows).pivot(index='regola', columns='gruppo', values=['ecc_pp', 't']).round(2); print(G.to_string())
R.to_csv(f'{OUT}/a_industrie.csv', index=False); pd.DataFrame(per_rows).to_csv(f'{OUT}/a_periodi.csv', index=False)
pd.DataFrame(reg_rows).to_csv(f'{OUT}/a_regioni.csv', index=False)
# ---- portafogli trimestrali in euro, 0,5% di costo: tutte le societa' delle industrie segnalate a pesi uguali
C2 = C[C.elig].copy()
out = {}
for r in RULES + ['UNIV_IDONEO']:
    sel = C2[r] if r != 'UNIV_IDONEO' else pd.Series(True, index=C2.index)
    q, tv = portfolio(C2, sel)
    out[r] = q
Q = pd.DataFrame(out)
Q.to_pickle(f'{OUT}/a_portafogli.pkl')
prow = []
for r in Q:
    q = Q[r]; d = q.index
    prow.append({'regola': r, '2012-16': cagr(q[(d <= '2016-09-30')]), '2017-21': cagr(q[(d > '2016-09-30') & (d <= '2021-09-30')]),
                 '2022-26': cagr(q[d > '2021-09-30']), '2012-26': cagr(q), 'perdita_max': maxdd(q),
                 'diff_vs_univ_t': nw_t((q - Q['UNIV_IDONEO']).values, 4)})
PR = pd.DataFrame(prow); print(PR.round(3).to_string()); PR.to_csv(f'{OUT}/a_portafogli.csv', index=False)
