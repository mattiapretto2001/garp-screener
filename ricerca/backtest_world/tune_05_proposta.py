# tune_05: proposta a due livelli.
# (a) GARP "core": griglia dichiarata in anticipo (108 combinazioni), scelta SOLO sul 2012-19, poi letta su 2020-24 e 2025-26.
#     Controllo del caso: (i) correlazione fra la classifica delle combinazioni nel 2012-19 e dopo; (ii) per le aggiunte
#     proposte, confronto con 500 "sfoltimenti a caso" del GARP attuale della stessa entita'.
# (b) Radar: regole dichiarate prima di guardare i risultati fuori campione, per titoli che il GARP esclude.
import pandas as pd, numpy as np, itertools
def spearmanr(a, b):
    class _R: pass
    r = _R(); r.correlation = pd.Series(list(a)).rank().corr(pd.Series(list(b)).rank()); return r
from tune_common import *
from tune_common import mask, score, BASE_P, W0
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400)
F = pd.read_pickle(f'{BASE}/res/tune_panel.pkl')
UNI = ~F.excl_sector
ru, _ = run(F, UNI)


def extra_mask(p):
    m = mask(F, p)
    if p.get('hi52') is not None: m &= (F.hi52 >= p['hi52']).fillna(False)
    if p.get('dsh') is not None: m &= (F.dshares < p['dsh']).fillna(True)
    return m


def stats(m, r, n):
    out = {}
    for per, (a, b) in PERIODS.items():
        ds = (F.date >= a) & (F.date <= b); X = F[m & ds & F.f12.notna()]
        out[per] = dict(n=n[(n.index >= a) & (n.index <= b)].mean(), cagr=cagr(r, a, b), vs_univ=cagr(r, a, b) - cagr(ru, a, b),
                        W5=X.W5.mean(), L20=X.L20.mean(), L50=X.L50.mean())
    return out


# ------------------------------------------------------------------ (a) griglia core
G = []
grid = list(itertools.product([None, 0.7, 0.8], [None, 0.05], [0.05, 0.10, 0.20], [0.10, 0.15, 0.20], [2.0, 3.0]))
SER = {}
for hi, dsh, rq, roe, peg in grid:
    p = dict(BASE_P, hi52=hi, dsh=dsh, revq=rq, roe=roe, peg=peg)
    m = extra_mask(p); r, n = run(F, m)
    st = stats(m, r, n)
    key = (hi, dsh, rq, roe, peg); SER[key] = r
    G.append(dict(hi52=hi, dsh=dsh, revq=rq, roe=roe, peg=peg, **{f'{k}_{per}': v for per, d in st.items() for k, v in d.items()}))
G = pd.DataFrame(G)
G.to_csv(f'{BASE}/res/tune_griglia_core.csv', index=False)
print('combinazioni', len(G))
ok = G['n_2012-19'] >= 15
rho1 = spearmanr(G.loc[ok, 'vs_univ_2012-19'], G.loc[ok, 'vs_univ_2020-24']).correlation
rho2 = spearmanr(G.loc[ok, 'vs_univ_2012-19'], G.loc[ok, 'vs_univ_2025-26']).correlation
rho3 = spearmanr(G.loc[ok, 'vs_univ_2020-24'], G.loc[ok, 'vs_univ_2025-26']).correlation
print(f'correlazione classifiche: 12-19 vs 20-24 {rho1:.2f}; 12-19 vs 25-26 {rho2:.2f}; 20-24 vs 25-26 {rho3:.2f}')
best = G[ok].sort_values('vs_univ_2012-19', ascending=False)
cur = G[(G.hi52.isna()) & (G.dsh.isna()) & (G.revq == 0.05) & (G.roe == 0.15) & (G.peg == 2.0)]
cols = ['hi52', 'dsh', 'revq', 'roe', 'peg'] + [f'{k}_{p}' for p in PERIODS for k in ['n', 'vs_univ', 'W5', 'L20']]
print('attuale'); print(cur[cols].round(3).to_string())
print('migliori 10 nel 2012-19'); print(best[cols].head(10).round(3).to_string())
for per in PERIODS:
    print(per, 'percentile della scelta IS fra le combinazioni:', round((G.loc[ok, f'vs_univ_{per}'] < best.iloc[0][f'vs_univ_{per}']).mean(), 2),
          'mediana griglia', round(G.loc[ok, f'vs_univ_{per}'].median(), 3))
# effetto medio di ogni scelta (marginale sulla griglia), per periodo: robusto se stesso segno ovunque
for c in ['hi52', 'dsh', 'revq', 'roe', 'peg']:
    print(c); print(G[ok].fillna({'hi52': 0, 'dsh': 9}).groupby(c)[[f'vs_univ_{p}' for p in PERIODS] + [f'n_{p}' for p in PERIODS]].mean().round(3).to_string())

# ------------------------------------------------------------------ varianti core da confrontare (stabilite dalla griglia)
VARS = {'attuale': dict(BASE_P),
        '+ vicino ai massimi (>=70% max 52 sett.)': dict(BASE_P, hi52=0.7),
        '+ niente diluizione (azioni <+5%/anno)': dict(BASE_P, dsh=0.05),
        '+ entrambi': dict(BASE_P, hi52=0.7, dsh=0.05)}
rows = []
base_m = extra_mask(VARS['attuale']); base_r, base_n = run(F, base_m)
sc_base = score(F, base_m); base_top, _ = run(F, base_m, topn=30, score=sc_base)
rng = np.random.default_rng(7)
for name, p in VARS.items():
    m = extra_mask(p); r, n = run(F, m)
    sc = score(F, m); rt, _ = run(F, m, topn=30, score=sc)
    st = stats(m, r, n)
    # placebo: togliere a caso dal GARP attuale la stessa quota di titoli che toglie la regola
    keep = (m & base_m).groupby(F.date).sum() / base_m.groupby(F.date).sum().replace(0, np.nan)
    plac = {per: [] for per in PERIODS}
    if name != 'attuale':
        B = F[base_m]
        for it in range(300):
            u = rng.random(len(B))
            fr = B.date.map(keep).fillna(1).values
            mm = pd.Series(False, index=F.index); mm[B.index[u < fr]] = True
            rr, _ = run(F, mm)
            for per, (a, b) in PERIODS.items(): plac[per].append(cagr(rr, a, b))
    for per, (a, b) in PERIODS.items():
        d = (r - base_r)[(r.index >= a) & (r.index <= b)]
        rows.append(dict(variante=name, periodo=per, **st[per], cagr_top30=cagr(rt, a, b),
                         d_vs_attuale=cagr(r, a, b) - cagr(base_r, a, b), t=tstat(d),
                         pct_vs_caso=np.mean(np.array(plac[per]) < cagr(r, a, b)) if plac[per] else np.nan))
    for reg in ['USA', 'Europa', 'Asia']:
        rm = m & (F.reg == reg); rb = base_m & (F.reg == reg)
        r1, _ = run(F, rm); r0, _ = run(F, rb)
        for per, (a, b) in PERIODS.items():
            rows.append(dict(variante=name, periodo=f'{per} {reg}', d_vs_attuale=cagr(r1, a, b) - cagr(r0, a, b), cagr=cagr(r1, a, b)))
V = pd.DataFrame(rows); V.to_csv(f'{BASE}/res/tune_core_varianti.csv', index=False)
print(V.round(3).to_string())

# ------------------------------------------------------------------ punteggio: aggiungere la vicinanza ai massimi / le azioni
SC = {'attuale': W0,
      'con momentum (max 52 sett. 15)': {**{k: v * 0.85 for k, v in W0.items()}, 'hi52': 15},
      'con diluizione (azioni 15)': {**{k: v * 0.85 for k, v in W0.items()}, 'dshares_neg': 15},
      'senza PEG': {k: v for k, v in W0.items() if k != 'peg'}}
F['dshares_neg'] = -F.dshares
rows = []
for name, W in SC.items():
    s = score(F, base_m, W); rt, _ = run(F, base_m, topn=30, score=s)
    for per, (a, b) in PERIODS.items():
        d = (rt - base_top)[(rt.index >= a) & (rt.index <= b)]
        rows.append(dict(punteggio=name, periodo=per, cagr_top30=cagr(rt, a, b), d=cagr(rt, a, b) - cagr(base_top, a, b), t=tstat(d)))
S = pd.DataFrame(rows); S.to_csv(f'{BASE}/res/tune_punteggi.csv', index=False); print(S.round(3).to_string())

# ------------------------------------------------------------------ (b) radar
q_ok = ((F.roe > 0.15) & (F.equity > 0) & (F.de < 1) & (F.fcf_ttm > 0)).fillna(False)
RADAR = {
    'R1 crescita forte, PEG alto o assente': (~F.excl_sector & q_ok & (F.revq > 0.20) & (F.rev_cagr > 0.10).fillna(False)),
    'R2 qualita\' alta in tendenza, senza PEG basso': (~F.excl_sector & ((F.roe > 0.20) & (F.de < 1) & (F.fcf_ttm > 0) & (F.revq > 0.05)).fillna(False) & (F.hi52 >= 0.8).fillna(False)),
    'R3 ipercrescita in tendenza (anche in perdita)': (~F.excl_sector & (F.revq > 0.25).fillna(False) & (F.rev_cagr > 0.15).fillna(False) & (F.hi52 >= 0.7).fillna(False) & (F.dshares < 0.10).fillna(False)),
    'R4 quasi-GARP (1 filtro mancato) vicino ai massimi': ((F.n_fail == 1) & ~F.excl_sector & (F.hi52 >= 0.75).fillna(False)),
}
RADAR['R1+R2+R4 (unione)'] = RADAR['R1 crescita forte, PEG alto o assente'] | RADAR['R2 qualita\' alta in tendenza, senza PEG basso'] | RADAR['R4 quasi-GARP (1 filtro mancato) vicino ai massimi']
RADAR['tutte (R1-R4)'] = RADAR['R1+R2+R4 (unione)'] | RADAR['R3 ipercrescita in tendenza (anche in perdita)']
med = F.groupby('date').f12.transform('median')
rows = []
Wtot = F[F.W5].groupby('per').size(); Mtot = F[F.MB3].groupby('per').size()
for name, m0 in list(RADAR.items()) + [('GARP attuale', base_m)]:
    m = m0 & ~base_m if name != 'GARP attuale' else m0
    r, n = run(F, m)
    for per, (a, b) in list(PERIODS.items()) + [('2012-26', ('2011-12-31', '2026-09-30'))]:
        ds = (F.date >= a) & (F.date <= b); X = F[m & ds & F.f12.notna()]
        ex = (X.f12 - med[X.index])
        rows.append(dict(regola=name, periodo=per, n=n[(n.index >= a) & (n.index <= b)].mean(), W5=X.W5.mean(), W10=X.W10.mean(),
                         L20=X.L20.mean(), L50=X.L50.mean(), MB3=F[m & ds & F.f36.notna()].MB3.mean(),
                         recall_W5=X.W5.sum() / F[ds].W5.sum(), recall_MB3=F[m & ds].MB3.sum() / max(F[ds].MB3.sum(), 1),
                         ex_med=ex.median(), cagr=cagr(r, a, b), vs_univ=cagr(r, a, b) - cagr(ru, a, b)))
    for reg in ['USA', 'Europa', 'Asia']:
        X = F[m & (F.reg == reg) & F.f12.notna()]
        rows.append(dict(regola=name, periodo=f'2012-26 {reg}', n=len(X) / F.date.nunique(), W5=X.W5.mean(), L20=X.L20.mean(),
                         ex_med=(X.f12 - med[X.index]).median()))
R = pd.DataFrame(rows); R.to_csv(f'{BASE}/res/tune_radar.csv', index=False)
print(R.round(3).to_string())
# base: universo senza settori esclusi
X = F[UNI & F.f12.notna()]
print('universo: W5', round(X.W5.mean(), 3), 'L20', round(X.L20.mean(), 3), 'MB3', round(F[UNI & F.f36.notna()].MB3.mean(), 3))
