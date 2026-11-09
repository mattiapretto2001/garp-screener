# temi_08: rumore delle segnalazioni, contributo dei fondamentali oltre al momentum, robustezza di BM e MOM, segnali di oggi
from temi_common import *
V = pd.read_pickle(f'{OUT}/ind_flags2.pkl')
CI = pd.read_pickle(f'{OUT}/comp_ind.pkl')
Fc = fv3.load(cols=['t', 'date', 'reg', 'reg_rob', 'fwd12_eur', 'xs12_reg', 'r_eur'])
C = CI.merge(Fc, on=['t', 'date']).merge(V[['ind', 'date', 'A', 'B', 'Bplus', 'W', 'MOM', 'CALDE', 'BM', 'MOM6', 'AMP']], on=['ind', 'date'], how='inner')
C['xs3'] = C.r_eur - C.groupby(['date', 'reg']).r_eur.transform('mean'); C.loc[C.date == C.date.max(), 'xs3'] = np.nan
I3 = C.groupby(['ind', 'date']).xs3.mean().rename('y3').reset_index()
V = V.merge(I3, on=['ind', 'date'], how='left')
V['rel12'] = V.y_xs - V.groupby('date').y_xs.transform('mean'); V['rel3'] = V.y3 - V.groupby('date').y3.transform('mean')
RULES = ['A', 'B', 'Bplus', 'W', 'MOM', 'CALDE', 'BM', 'MOM6', 'AMP']
rows = []
for r in RULES:
    f = V[V[r]]; nf = V[~V[r]]
    rows.append({'regola': r, 'segnalazioni': int(f.rel12.notna().sum()), 'battono_media_3m': (f.rel3.dropna() > 0).mean(), 'battono_media_12m': (f.rel12.dropna() > 0).mean(),
                 'fallite_12m(<-10pp)': (f.rel12.dropna() < -0.10).mean(), 'fallite_non_segn': (nf.rel12.dropna() < -0.10).mean(),
                 'disastro_12m(<-25pp)': (f.rel12.dropna() < -0.25).mean(), 'disastro_non_segn': (nf.rel12.dropna() < -0.25).mean(),
                 'boom_12m(>+25pp)': (f.rel12.dropna() > 0.25).mean(), 'boom_non_segn': (nf.rel12.dropna() > 0.25).mean()})
N = pd.DataFrame(rows); pd.set_option('display.width', 250); print(N.round(3).to_string()); N.to_csv(f'{OUT}/d_rumore.csv', index=False)
# Fama-MacBeth a livello industria: i fondamentali (punteggio B) aggiungono qualcosa al momentum dell'industria?
V['rkB'] = V.groupby('date').scoreB.rank(pct=True) - 0.5; V['rkM'] = V.groupby('date').mom_med.rank(pct=True) - 0.5
for yv, lag in (('rel3', 1), ('rel12', 4)):
    V['ry'] = V.groupby('date')[yv].rank(pct=True) - 0.5
    co = []
    for d, g in V[V.ry.notna()].groupby('date'):
        Z = np.c_[np.ones(len(g)), g.rkB.fillna(0), g.rkM.fillna(0)]
        b = np.linalg.lstsq(Z, g.ry.values, rcond=None)[0]; co.append({'date': d, 'B': b[1], 'MOM': b[2]})
    co = pd.DataFrame(co).set_index('date')
    print(yv, 'FM congiunta (rango esito su ranghi): B %.3f (t %.2f), MOM %.3f (t %.2f)' % (co.B.mean(), nw_t(co.B, lag), co.MOM.mean(), nw_t(co.MOM, lag)),
          '| per periodo B:', [round(co.B[[per3_of(x) == p for x in co.index]].mean(), 3) for p in PER3],
          'MOM:', [round(co.MOM[[per3_of(x) == p for x in co.index]].mean(), 3) for p in PER3])
# robustezza per gruppo regionale a 3 e 12 mesi (eccesso vs societa' idonee dello stesso gruppo)
C['xs_rob12'] = C.fwd12_eur - C.groupby(['date', 'reg_rob']).fwd12_eur.transform('mean')
C['xs_rob3'] = C.r_eur - C.groupby(['date', 'reg_rob']).r_eur.transform('mean'); C.loc[C.date == C.date.max(), 'xs_rob3'] = np.nan
rr = []
for r in ['B', 'MOM', 'BM']:
    for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia']:
        S = C[C[r] & (C.reg_rob == rg)]
        a = S.groupby('date').xs_rob3.mean().dropna(); b = S.groupby('date').xs_rob12.mean().dropna()
        rr.append({'regola': r, 'gruppo': rg, '3m_pp': 100 * a.mean(), 't3': nw_t(a, 1), '12m_pp': 100 * b.mean(), 't12': nw_t(b, 4)})
RR = pd.DataFrame(rr); print(RR.round(2).to_string()); RR.to_csv(f'{OUT}/d_regioni.csv', index=False)
# portafogli B, MOM, BM: paniere intero, 0,5% costi
Cp = C.copy(); out = {}
for r in ['B', 'MOM', 'BM']: out[r] = portfolio(Cp, Cp[r])
out['UNIV'] = portfolio(Cp, pd.Series(True, index=Cp.index))
for r, (q, tv) in out.items():
    d = q.index
    print(r, 'CAGR 2012-26 %.3f | 2012-16 %.3f 2017-21 %.3f 2022-26 %.3f | perdita max %.2f | rotazione media per trimestre %.2f | diff vs univ t %.2f' % (
        cagr(q), cagr(q[d <= '2016-09-30']), cagr(q[(d > '2016-09-30') & (d <= '2021-09-30')]), cagr(q[d > '2021-09-30']), maxdd(q), tv.mean(),
        nw_t((q - out['UNIV'][0]).values, 1)))
# segnali di oggi (30/09/2026)
last = V.date.max(); L = V[V.date == last].sort_values('scoreB', ascending=False)
L['pctB'] = L.scoreB.rank(pct=True); L['pctM'] = L.mom_med.rank(pct=True)
print('\nOggi', last.date())
print(L[L.B | L.MOM][['ind', 'n', 'B', 'MOM', 'BM', 'pctB', 'pctM', 'g_agg', 'accel_agg', 'qa', 'pos', 'd_pos2', 'd_marg', 'mom_med']].round(3).to_string(index=False))
L[L.B | L.MOM].to_csv(f'{OUT}/d_segnali_oggi.csv', index=False)
