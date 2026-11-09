# temi_07: test (c). Screener dei temi: le N migliori societa' dentro le industrie segnalate, con punteggio.
# Insieme candidato: societa' delle industrie segnalate da B o MOM (regole fissate in temi_02).
# Punteggi:
#   S1 'a priori'  : media dei ranghi di -dsh3, fcfy, hi52, -vol1y, rel_mom_ind (guardia comune dei report precedenti + leader;
#                    ATTENZIONE: scelta con dati 2012-2026 da altri agenti, quindi non e' fuori campione)
#   S2 'walk-forward': ogni anno, tra 16 variabili tengo quelle con |t|>=2 nella correlazione con rk12_reg dentro i temi,
#                    calcolata solo su date <= inizio anno - 4 trimestri; peso = segno. Fuori campione 2015-2026.
#   Varianti: N=25 con max 5 per industria; con e senza capitalizzazione >=2 Mld$; S2 applicato a TUTTE le industrie (controllo).
from temi_common import *
V = pd.read_pickle(f'{OUT}/ind_flags2.pkl')
CI = pd.read_pickle(f'{OUT}/comp_ind.pkl')
VARS = ['rel_mom_ind', 'rel_revg_ind', 'logmcap', 'roic', 'fcf_m', 'opm_avg5', 'n_loss_5y', 'hi52', 'vol1y', 'mom12_1', 'ev_sales',
        'fcfy', 'dsh3', 'revq', 'rev_cagr', 'accel_q']
Fc = fv3.load(cols=['t', 'date', 'name', 'reg_rob', 'fwd12_eur', 'rk12_reg', 'top5_reg', 'bot20_reg', 'crash50', 'r_eur', 'mcap_usd'] + VARS)
C = CI.merge(Fc, on=['t', 'date']).merge(V[['ind', 'date', 'B', 'MOM', 'BM', 'scoreB']], on=['ind', 'date'], how='inner')
C['tema'] = C.B | C.MOM
D = sorted(C.date.unique())
def xr(X, cols):  # ranghi 0-1 dentro la data, sull'insieme X
    return pd.DataFrame({c: X.groupby('date')[c].rank(pct=True) for c in cols}, index=X.index)
# ---- IC per data (insieme temi), per il walk-forward
T = C[C.tema]
ic = {}
for d, g in T[T.rk12_reg.notna()].groupby('date'):
    ic[d] = {v: g[v].corr(g.rk12_reg, method='spearman') for v in VARS}
IC = pd.DataFrame(ic).T
ICall = {}
for d, g in C[C.rk12_reg.notna()].groupby('date'):
    ICall[d] = {v: g[v].corr(g.rk12_reg, method='spearman') for v in VARS}
ICall = pd.DataFrame(ICall).T
def wf_weights(ICt, y):
    cut = pd.Timestamp(f'{y}-01-01') - pd.offsets.QuarterEnd(5)    # ultima data con esito noto all'inizio dell'anno y
    tr = ICt[ICt.index <= cut]
    if len(tr) < 8: return None
    w = {}
    for v in VARS:
        t = nw_t(tr[v]); 
        if np.isfinite(t) and abs(t) >= 2: w[v] = np.sign(tr[v].mean())
    return w
WL = []
def score_wf(X, ICt, tag):
    s = pd.Series(np.nan, index=X.index)
    for y in range(2015, 2027):
        w = wf_weights(ICt, y)
        if not w: continue
        m = X.date.dt.year == y
        R = xr(X[m], list(w))
        s[m] = sum(R[v] * (w[v]) + (0.5 if w[v] < 0 else 0) * 0 for v in w) / len(w)
        s[m] = sum((R[v] if w[v] > 0 else 1 - R[v]) for v in w) / len(w)
        WL.append({'insieme': tag, 'anno': y, 'variabili': ' '.join(('+' if w[v] > 0 else '-') + v for v in w)})
    return s
T = C[C.tema].copy()
R1 = xr(T, ['dsh3', 'fcfy', 'hi52', 'vol1y', 'rel_mom_ind'])
T['S1'] = (1 - R1.dsh3.fillna(.5) + R1.fcfy.fillna(.5) + R1.hi52.fillna(.5) + 1 - R1.vol1y.fillna(.5) + R1.rel_mom_ind.fillna(.5)) / 5
T['S2'] = score_wf(T, IC, 'temi')
A = C.copy(); A['S2'] = score_wf(A, ICall, 'tutte')
# S3 (ESPLORATIVA, aggiunta dopo aver visto S1/S2): walk-forward sulla correlazione con 'eccezionale' (top5_reg) invece del rango
ic5 = {}
for d, g in T[T.top5_reg.notna()].groupby('date'):
    ic5[d] = {v: g[v].corr(g.top5_reg.astype(float), method='spearman') for v in VARS}
IC5 = pd.DataFrame(ic5).T
T['S3'] = score_wf(T, IC5, 'temi-top5')
pd.DataFrame(WL).to_csv(f'{OUT}/c_pesi_wf.csv', index=False)
print(pd.DataFrame(WL).to_string())
def pick(X, sc, N=25, cap=5, minmc=0):
    X = X[X[sc].notna() & (X.mcap_usd >= minmc)].sort_values(sc, ascending=False)
    X = X[X.groupby(['date', 'ind']).cumcount() < cap]
    X = X[X.groupby('date').cumcount() < N]
    return X.index
res = {}; picks = {}
for lab, X, sc, mm in [('S1 a priori, temi', T, 'S1', 0), ('S2 walk-forward, temi', T, 'S2', 0), ('S2 walk-forward, temi, >=2 Mld$', T, 'S2', 2e9),
                       ('S1 a priori, temi, >=2 Mld$', T, 'S1', 2e9), ('S2 walk-forward, tutte le industrie', A, 'S2', 0),
                       ('S3 walk-forward eccezionali, temi (esplorativa)', T, 'S3', 0)]:
    ix = pick(X, sc, minmc=mm); picks[lab] = X.loc[ix]
    sel = pd.Series(False, index=C.index); sel[ix] = True
    res[lab] = portfolio(C, sel)[0]
res['Temi: tutte le societa\''] = portfolio(C, C.tema)[0]
res['Universo (industrie idonee)'] = portfolio(C, pd.Series(True, index=C.index))[0]
Q = pd.DataFrame(res); Q.to_pickle(f'{OUT}/c_portafogli.pkl')
U = Q['Universo (industrie idonee)']
rows = []
for c in Q:
    q = Q[c]; d = q.index
    o = {'portafoglio': c}
    for lab, a, b in [('2015-16', '2014-12-31', '2016-09-30'), ('2017-21', '2016-12-31', '2021-09-30'), ('2022-26', '2021-12-31', '2026-09-30'),
                      ('2015-26 (fuori campione)', '2014-12-31', '2026-09-30')]:
        m = (d >= a) & (d <= b); o[lab] = cagr(q[m]) if q[m].abs().sum() > 0 else np.nan
    m = d >= '2014-12-31'
    o['diff_vs_univ_2015-26'] = o['2015-26 (fuori campione)'] - cagr(U[m]); o['t'] = nw_t((q - U)[m], 1); o['perdita_max_2015-26'] = maxdd(q[m])
    if c in picks:
        P = picks[c]; P = P[P.date >= '2014-12-31']
        o['top5'] = P.top5_reg.mean(); o['bot20'] = P.bot20_reg.mean(); o['crollo50'] = P.crash50.mean(); o['titoli'] = P.groupby('date').size().mean()
    rows.append(o)
PR = pd.DataFrame(rows); pd.set_option('display.width', 250); print(PR.round(3).to_string()); PR.to_csv(f'{OUT}/c_screener.csv', index=False)
base = C[(C.date >= '2014-12-31') & C.fwd12_eur.notna()]
print('base universo idoneo 2015-25: top5 %.3f bot20 %.3f crollo %.3f' % (base.top5_reg.mean(), base.bot20_reg.mean(), base.crash50.mean()))
bt = base[base.tema]; print('base temi: top5 %.3f bot20 %.3f crollo %.3f' % (bt.top5_reg.mean(), bt.bot20_reg.mean(), bt.crash50.mean()))
# ---- contro il caso: 300 estrazioni di 25 titoli a caso (max 5 per industria non imposto) dentro l'insieme temi, 2015-2026, senza costi
rng = np.random.default_rng(7)
Tq = T[T.date >= '2014-12-31'][['date', 'r_eur']].copy(); Tq['r_eur'] = Tq.r_eur.fillna(0)
grp = {d: g.r_eur.values for d, g in Tq.groupby('date')}
rand = []
for k in range(300):
    q = [np.mean(rng.choice(v, size=min(25, len(v)), replace=False)) for d, v in sorted(grp.items())]
    rand.append(cagr(q))
rand = np.array(rand)
for lab in ['S1 a priori, temi', 'S2 walk-forward, temi', 'S2 walk-forward, temi, >=2 Mld$', 'S3 walk-forward eccezionali, temi (esplorativa)']:
    P = picks[lab]; P = P[P.date >= '2014-12-31']
    q = P.assign(r=P.r_eur.fillna(0)).groupby('date').r.mean()
    print(lab, 'senza costi %.3f; quota estrazioni a caso battute: %.2f (caso: mediana %.3f, 5-95%% %.3f-%.3f)' % (cagr(q), (rand < cagr(q)).mean(), np.median(rand), *np.percentile(rand, [5, 95])))
# ---- elenco di oggi (30/09/2026) per illustrazione
last = C.date.max()
for lab in ['S2 walk-forward, temi, >=2 Mld$', 'S1 a priori, temi, >=2 Mld$']:
    P = picks[lab]; P = P[P.date == last]
    print('\n', lab, last.date()); print(P[['t', 'name', 'ind', 'mcap_usd']].assign(mcap_mld=lambda x: (x.mcap_usd / 1e9).round(1)).drop(columns='mcap_usd').to_string(index=False))
    P[['t', 'name', 'ind', 'mcap_usd']].to_csv(f'{OUT}/c_lista_oggi_{"S2" if "S2" in lab else "S1"}.csv', index=False)
