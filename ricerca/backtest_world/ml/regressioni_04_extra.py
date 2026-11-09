# regressioni_04: approfondimenti dopo il walk-forward (tutte varianti contate nel report)
# (a) decili fuori campione: rango medio vs rendimento medio/mediano
# (b) classificazione delle variabili per effetto sulle due code (FM lineari top5_reg / bot20_reg, |t|>=2)
# (c) elastic net walk-forward sull'eccesso di rendimento in % (winsorizzato) invece del rango
# (d) punteggio a due lati: rango(P top5) + rango(1 - P bot20)
# (e) "prima il cancello, poi il punteggio": elastic net addestrato solo dentro un cancello (profilo) e top 30 vs core
import sys, os, time, warnings, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import GroupKFold
warnings.filterwarnings('ignore')
T0 = time.time(); OUT = rc.HERE + '/reg_out'
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
log = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.append(s)
M = rc.load().reset_index(drop=True)
F = fv3.load(cols=['revq', 'revg_ttm', 'hi52', 'n_fail', 'roe', 'de']); M[['raw_' + c for c in F.columns]] = F.values
P = fv3.PREDICTORS; ZP = ['z_' + c for c in P]
PR = pd.read_pickle(f'{OUT}/enet_pred.pkl')
for k in ['enet_rk', 'enet_t5', 'enet_b20', 'fmcomp']: M[k] = PR[k].values
for c in ['top5_reg', 'bot20_reg', 'crash50']: M[c] = M[c].astype(float)
M['y_rk'] = (M.rk12_reg - 0.5) * rc.S12
M['y_xs'] = fv3.winsor(M.assign(xs=M.xs12_reg), ['xs'])['xs']

# (a) decili fuori campione
E = M[M.enet_rk.notna() & M.rk12_reg.notna()].copy()
rows = []
for k in ['enet_rk', 'enet_b20', 'enet_t5']:
    s = -E[k] if k == 'enet_b20' else E[k]
    E['dec'] = s.groupby(E.date).transform(lambda x: pd.qcut(x.rank(method='first'), 10, labels=False)) + 1
    g = E.groupby('dec')
    T = pd.DataFrame({'rango': g.rk12_reg.mean(), 'rend_medio': g.fwd12_eur.mean() * 100, 'rend_mediano': g.fwd12_eur.median() * 100,
                      'top5': g.top5_reg.mean() * 100, 'bot20': g.bot20_reg.mean() * 100, 'crash50': g.crash50.mean() * 100,
                      'vol1y': E.assign(v=fv3.load(cols=['vol1y']).vol1y.reindex(E.index)).groupby('dec').v.median()})
    T['modello'] = k; rows.append(T)
    say('DECILI', k); say(T.round(3).to_string())
pd.concat(rows).to_csv(f'{OUT}/oos_decili.csv')

# (b) quadranti
S = pd.read_csv(f'{OUT}/fm_sintesi.csv', index_col=0)
def quad(r):
    up = r.t_top5 >= 2; dn = r.t_top5 <= -2; good = r.t_bot20 <= -2; bad = r.t_bot20 >= 2
    if up and good: return 'A: piu eccezionali e meno disastri'
    if up and bad: return 'B: lotteria (piu di entrambi)'
    if dn and good: return 'C: difensiva (meno di entrambi)'
    if dn and bad: return 'D: peggiora entrambi'
    if up: return 'A-: piu eccezionali, disastri invariati'
    if good: return 'C-: meno disastri, eccezionali invariati'
    if dn: return 'D-: meno eccezionali'
    if bad: return 'D-: piu disastri'
    return '-'
S['quadrante'] = S.apply(quad, axis=1)
say(S.sort_values('quadrante')[['quadrante', 't_top5', 't_bot20', 't_crash', 't_lg_top5', 't_lg_bot20', 't_rk']].round(1).to_string())
S[['quadrante', 't_top5', 't_bot20', 't_crash', 't_lg_top5', 't_lg_bot20', 't_rk']].to_csv(f'{OUT}/quadranti.csv')

# (c) + (e) walk-forward aggiuntivi
X = M[ZP].fillna(0).values
dates = M.date.values
gates = {
    'tutti_xs': np.ones(len(M), bool),
    'cancello_crescita_profittevole': (~M.excl_sector & (M.ni_ttm > 0) & (M.raw_revg_ttm >= 0.10) & (M.mcap_usd >= 2e9)).values,
    'cancello_crescita20': (~M.excl_sector & (M.raw_revg_ttm >= 0.20) & (M.mcap_usd >= 2e9)).values,
}
pred = {k: np.full(len(M), np.nan) for k in gates}
for yr, train, test in fv3.walk_forward_splits(M.date, first_test_year=2015, embargo_q=4):
    tr = np.isin(dates, np.array(train, dtype='datetime64[ns]')); te = np.isin(dates, np.array(test, dtype='datetime64[ns]'))
    for k, gm in gates.items():
        ycol = 'y_xs' if k == 'tutti_xs' else 'y_rk'
        y = M[ycol].values; ok = tr & gm & ~np.isnan(y)
        yrs = pd.DatetimeIndex(dates[ok]).year.values
        cv = list(GroupKFold(n_splits=min(5, len(set(yrs)))).split(X[ok], groups=yrs))
        m = ElasticNetCV(l1_ratio=0.5, alphas=25, cv=cv, n_jobs=4, tol=1e-3, max_iter=3000).fit(X[ok], y[ok])
        pred[k][te & gm] = m.predict(X[te & gm])
        if yr in (2015, 2020, 2025):
            nz = pd.Series(m.coef_, index=P); nz = nz[nz.abs() > 1e-9].sort_values()
            say(yr, k, 'righe', ok.sum(), 'var', len(nz), 'principali:', ', '.join(f'{i}{v:+.3f}' for i, v in pd.concat([nz.head(4), nz.tail(5)]).items()))
for k in gates: M['p_' + k] = pred[k]
M['p_duelati'] = M.groupby('date').enet_t5.rank(pct=True) + M.groupby('date').enet_b20.rank(pct=True, ascending=False)
M[['t', 'date'] + ['p_' + k for k in gates] + ['p_duelati']].to_pickle(f'{OUT}/extra_pred.pkl')

# valutazione
V = M[M.enet_rk.notna() & (M.date <= '2026-06-30')].copy()
dd = sorted(V.date.unique())
uni = V.groupby('date').r_eur.mean()
PT = {}
PT['core di oggi'] = rc.port(V, lambda g: g[g.core], dd)
PT['xs: top30 >=2Mld'] = rc.port(V, lambda g: g[g.mcap_usd >= 2e9].nlargest(30, 'p_tutti_xs'), dd)
PT['xs: decile'] = rc.port(V, lambda g: g[g.p_tutti_xs >= g.p_tutti_xs.quantile(.9)], dd)
PT['due lati: top30 >=2Mld'] = rc.port(V, lambda g: g[g.mcap_usd >= 2e9].nlargest(30, 'p_duelati'), dd)
PT['due lati: decile'] = rc.port(V, lambda g: g[g.p_duelati >= g.p_duelati.quantile(.9)], dd)
for k in ['cancello_crescita_profittevole', 'cancello_crescita20']:
    PT[f'{k}: tutto il cancello'] = rc.port(V, lambda g, k=k: g[g['p_' + k].notna()], dd)
    PT[f'{k}: top30 punteggio'] = rc.port(V, lambda g, k=k: g[g['p_' + k].notna()].nlargest(30, 'p_' + k), dd)
    PT[f'{k}: top30 + no disastro'] = rc.port(V, lambda g, k=k: g[g['p_' + k].notna() & (g.enet_b20 <= g.enet_b20.quantile(.5))].nlargest(30, 'p_' + k), dd)
# il core stesso filtrato dal punteggio anti-disastro (meta' piu' sicura dell'universo)
PT['core + no disastro (meta sicura)'] = rc.port(V, lambda g: g[g.core & (g.enet_b20 <= g.enet_b20.quantile(.5))], dd)
PT['core + no disastro (togli 20% peggiore)'] = rc.port(V, lambda g: g[g.core & (g.enet_b20 <= g.enet_b20.quantile(.8))], dd)
ST = pd.DataFrame({k: rc.pstats(v, uni) for k, v in PT.items()}).T
for c in ST.columns:
    if c not in ('titoli', 't'): ST[c] = ST[c] * 100
say(ST.round(2).to_string())
core_r = PT['core di oggi'].r
for k in PT:
    if k.startswith('core di'): continue
    d = PT[k].r - core_r
    say('vs core: %-55s %+.1f punti/anno (t %.2f)' % (k, 100 * ((1 + PT[k].r).prod() ** (4 / len(d)) - (1 + core_r).prod() ** (4 / len(d))), fv3.nw_t(d, 2)))
ST.to_csv(f'{OUT}/extra_portafogli.csv')
open(f'{OUT}/regressioni_04.log', 'w').write('\n'.join(log))
say('fine', round(time.time() - T0))
