# avv_uni_04 (verifica avversariale): anno per anno, n_beat4 a parita' di copertura, verdetto senza Asia e con il solo
# periodo pulito, forme a U, crescita per decili nel periodo pulito, spread di rendimento con SE prudenti.
import numpy as np, pandas as pd
from univariata_common import *
F = load_dev(); P = fv3.PREDICTORS
SER = pd.read_pickle(f'{OUT}/ic_series.pkl'); S0 = pd.read_csv(f'{OUT}/ic_summary.csv')
dates = np.sort(F.date.unique()); DI = {d: i for i, d in enumerate(dates)}; ND = len(dates); F['di'] = F.date.map(DI).astype(int)
pd.set_option('display.width', 250)
def hh_t(x, L=3):
    x = pd.Series(x).dropna().values.astype(float); T = len(x); e = x - x.mean(); v = e @ e / T
    for l in range(1, L + 1): v += 2 * (e[l:] @ e[:-l]) / T
    return x.mean() / np.sqrt(v / T) if v > 0 else np.nan
# 1) anno per anno (anno di formazione) per le variabili chiave su rk
V = ['dsh3', 'n_beat4', 'runway_y', 'roic', 'hist_y', 'fcfy', 'opm_std5', 'capex_int']
Y = pd.DataFrame({v: SER[('pool', v, 'rk')] for v in V}); Y['anno'] = pd.to_datetime(Y.index).year
A = Y.groupby('anno')[V].mean()
print('IC medio per anno di formazione (x100):'); print((100 * A).round(1).to_string())
sgn = np.sign(Y[V].mean())
tot = (Y[V] * sgn).sum()
w = (Y[V] * sgn)[(Y.index >= pd.Timestamp('2021-03-31')) & (Y.index <= pd.Timestamp('2022-12-31'))].sum()
print('quota della somma degli IC dovuta alle 8 date 2021-03..2022-12 (finestre che coprono il 2022):'); print((w / tot).round(2).to_string())
# 2) n_beat4 con copertura piena (n_est4 == 4) e n_est4 come semplice indicatore di copertura
X = F[F.n_est4 == 4]; m = F.n_est4.notna()
for name, Z in [('n_est4==4', X), ('n_est4 presente', F[m])]:
    r = pct_rank(Z, ['n_beat4'], ['date', 'reg'])['n_beat4'].values.astype(float)
    s = pd.Series(group_stat(r, Z.rk12_reg.values.astype(float), Z.di.values, 'ic', G=ND)).dropna()
    print(f'n_beat4 IC su {name}: {s.mean():+.4f} t {fv3.nw_t(s,4):+.2f}  righe {len(Z)}')
print('quota n_est4==4 fra le presenti:', round((F.n_est4 == 4).sum() / F.n_est4.notna().sum(), 3))
print('rk medio per n_est4:', F.groupby('n_est4').rk12_reg.mean().round(3).to_dict(), ' NaN:', round(F[F.n_est4.isna()].rk12_reg.mean(), 3))
# 3) verdetto rifatto: senza Asia (sopravvissute) e con periodo pulito >=2018 al posto del 2012-16
rows = []
for v in P:
    for tk in TGT_MAIN:
        s = SER[('pool', v, tk)].dropna(); sg = np.sign(s.mean()); t = fv3.nw_t(s, 4)
        clean = s[s.index >= pd.Timestamp('2018-03-31')]
        r3 = [SER[('reg', v, tk, r)].dropna() for r in ['USA grandi', 'USA piccole/medie', 'Europa']]
        n3 = sum(np.sign(z.mean()) == sg for z in r3 if len(z) >= 12)
        p2 = S0[(S0['var'] == v) & (S0.tgt == tk)][['per_2017-21', 'per_2022-26']].values[0]
        ok = abs(t) >= 2.5 and np.sign(clean.mean()) == sg and abs(fv3.nw_t(clean, 4)) >= 2.0 and n3 == 3 and all(np.sign(p2) == sg)
        rows.append(dict(var=v, tgt=tk, t=t, t_clean=fv3.nw_t(clean, 4), n3=n3, solida_rifatta=ok))
R = pd.DataFrame(rows)
orig = S0.set_index(['var', 'tgt']).verdetto
R['solida_orig'] = [orig.loc[(a, b)] == 'solida' for a, b in zip(R['var'], R.tgt)]
print('\nsolide: originale vs rifatto (t>=2,5 sul totale, t>=2 e stesso segno su date>=2018, 3/3 fra USA grandi, USA p/m, Europa, segno 2017-21 e 2022-26):')
print(R.groupby('tgt')[['solida_orig', 'solida_rifatta']].sum())
k = R[(R.tgt == 'rk') & (R.solida_orig != R.solida_rifatta)]
print(k.round(2).to_string(index=False))
print('solide rifatte su rk:', R[(R.tgt == 'rk') & R.solida_rifatta]['var'].tolist())
R.to_csv(f'{OUT}/avv_verdetto_rifatto.csv', index=False)
# 4) forme a U su top5 / bot20
Q = pd.read_csv(f'{OUT}/quintili.csv')
for tk in ['top5', 'bot20', 'rk']:
    print('forme', tk, Q[Q.tgt == tk].forma.value_counts().to_dict())
# 5) crescita per decili: periodo pulito e sopravvissute
G = F.sample(frac=1.0, random_state=7).sort_values('date', kind='stable')
for v in ['rev_cagr', 'revg_ttm']:
    gv = G[v].groupby([G.date, G.reg], observed=True); rr = (gv.rank(method='first') - 0.5) / gv.transform('count')
    G['_d'] = np.clip(np.ceil(rr * 10), 1, 10)
    for nm, m in [('<=2017', G.date <= '2017-12-31'), ('>=2018', G.date >= '2018-03-31'), ('>=2018 USA', (G.date >= '2018-03-31') & (G.reg == 'USA'))]:
        d = G[m].groupby(['date', '_d']).agg(rk=('rk12_reg', 'mean'), cr=('crash50', 'mean')).groupby('_d').mean()
        print(f'{v} {nm}: rango per decile', ' '.join(f'{x:.3f}' for x in d.rk.values), '| crolli D1/D5/D10', f'{d.cr.iloc[0]:.3f}/{d.cr.iloc[4]:.3f}/{d.cr.iloc[9]:.3f}')
# 6) spread di rendimento (xs12w, eccesso sulla regione) per quintili: Q5-Q1 e Q1/Q5 contro la media
fwdq = G.groupby('date').fwd12_eur.transform(lambda s: s.rank(pct=True))
for v in ['dsh3', 'n_beat4', 'surp_mean4', 'cash_mcap', 'runway_y', 'roic', 'hist_y']:
    gv = G[v].groupby([G.date, G.reg], observed=True); rr = (gv.rank(method='first') - 0.5) / gv.transform('count')
    G['_q'] = np.clip(np.ceil(rr * 5), 1, 5)
    for nm, m in [('tutto', G.date.notna()), ('>=2018', G.date >= '2018-03-31'), ('senza top1%', fwdq <= 0.99), ('>=2 mld', G.mcap_usd >= 2e9)]:
        M = G[m & G._q.notna()].groupby(['date', '_q']).xs12w.mean().unstack()
        d = M[5] - M[1]
        print(f'{v:10s} {nm:12s} Q1 {100*M[1].mean():+5.1f} (t {fv3.nw_t(M[1],4):+.1f})  Q5 {100*M[5].mean():+5.1f} (t {fv3.nw_t(M[5],4):+.1f})  Q5-Q1 {100*d.mean():+5.1f} t NW4 {fv3.nw_t(d,4):+.1f} HH {hh_t(d):+.1f}')
Qx = Q[Q.tgt == 'xs']
print('\nQ5-Q1 su rendimento: quante |t|>=2 su 81:', int((Qx.t51.abs() >= 2).sum()), ' |t|>=2,5:', int((Qx.t51.abs() >= 2.5).sum()), ' |t|>=3:', int((Qx.t51.abs() >= 3).sum()))
print(Qx[Qx.t51.abs() >= 2][['var', 'q51', 't51']].round(3).to_string(index=False))
