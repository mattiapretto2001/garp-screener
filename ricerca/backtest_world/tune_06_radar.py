# tune_06: radar dei potenziali eccezionali esclusi dal GARP. Griglia dichiarata (192 regole), scelta sul 2012-19 con criterio
# fissato prima: massima quota di top 5% fra le regole con 8-40 titoli medi per data e perdenti (bottom 20%) <= 25%.
# Poi lettura 2020-24 e 2025-26 senza ritocchi; correlazione delle classifiche fra periodi; confronto con estrazioni a caso.
import pandas as pd, numpy as np, itertools
from tune_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
F = pd.read_pickle(f'{BASE}/res/tune_panel.pkl')
base_m = mask(F, BASE_P)
POOL = ~F.excl_sector & ~base_m
ru, _ = run(F, ~F.excl_sector)
grid = list(itertools.product([0.15, 0.25, 0.40], [None, 0.15], [None, 0.7], [False, True], [None, 0.10], [False, True], [None, 10e9]))
rows, MASKS = [], {}
for rq, cg, hi, prof, dsh, dop, mc in grid:
    m = POOL & (F.revq > rq).fillna(False)
    if cg is not None: m &= (F.rev_cagr > cg).fillna(False)
    if hi is not None: m &= (F.hi52 >= hi).fillna(False)
    if prof: m &= (F.ni_ttm > 0).fillna(False)
    if dsh is not None: m &= (F.dshares < dsh).fillna(True)
    if dop: m &= (F.d_opm > 0).fillna(False)
    if mc is not None: m &= (F.mcap_usd < mc)
    k = (rq, cg, hi, prof, dsh, dop, mc); MASKS[k] = m
    r = dict(revq=rq, cagr=cg, hi52=hi, utile=prof, dsh=dsh, margine_su=dop, cap_max=mc)
    for per, (a, b) in PERIODS.items():
        ds = (F.date >= a) & (F.date <= b); X = F[m & ds & F.f12.notna()]
        r[f'n_{per}'] = (m & ds).sum() / ds[ds].groupby(F.date[ds]).ngroups if ds.any() else np.nan
        r[f'W5_{per}'] = X.W5.mean(); r[f'L20_{per}'] = X.L20.mean(); r[f'MB3_{per}'] = F[m & ds & F.f36.notna()].MB3.mean()
    rows.append(r)
G = pd.DataFrame(rows); G.to_csv(f'{BASE}/res/tune_griglia_radar.csv', index=False)
ok = G['n_2012-19'].between(8, 40) & (G['L20_2012-19'] <= 0.25)
print('regole', len(G), 'ammesse in calibrazione', ok.sum())
for a, b in [('2012-19', '2020-24'), ('2012-19', '2025-26'), ('2020-24', '2025-26')]:
    print('correlazione classifica W5', a, b, round(G[f'W5_{a}'].rank().corr(G[f'W5_{b}'].rank()), 2))
B = G[ok].sort_values('W5_2012-19', ascending=False)
cols = list(G.columns[:7]) + [f'{k}_{p}' for p in PERIODS for k in ['n', 'W5', 'L20', 'MB3']]
print(B[cols].head(12).round(3).to_string())
for per in ['2020-24', '2025-26']:
    print(per, 'scelta IS: percentile W5 nella griglia', round((G[f'W5_{per}'] < B.iloc[0][f'W5_{per}']).mean(), 2), 'mediana griglia', round(G[f'W5_{per}'].median(), 3))
# effetto marginale di ogni condizione sulla quota di top 5% e di perdenti
for c in ['revq', 'cagr', 'hi52', 'utile', 'dsh', 'margine_su', 'cap_max']:
    print(c); print(G.fillna({'cagr': 0, 'hi52': 0, 'dsh': 9, 'cap_max': 0}).groupby(c)[[f'W5_{p}' for p in PERIODS] + [f'L20_{p}' for p in PERIODS] + ['n_2020-24']].mean().round(3).to_string())
# estrazioni a caso: stessa numerosita' per data, dal pool escluso dal GARP (stessa regione): quanto spesso W5 >= scelta
best = tuple(B.iloc[0][['revq', 'cagr', 'hi52', 'utile', 'dsh', 'margine_su', 'cap_max']].where(lambda s: s.notna(), None))
best = (float(best[0]), None if best[1] is None else float(best[1]), None if best[2] is None else float(best[2]), bool(best[3]),
        None if best[4] is None else float(best[4]), bool(best[5]), None if best[6] is None else float(best[6]))
m = MASKS[best]
rng = np.random.default_rng(3)
P = F[POOL & F.f12.notna()]
for per, (a, b) in PERIODS.items():
    ds = (P.date >= a) & (P.date <= b)
    sel = F[m & F.f12.notna() & (F.date >= a) & (F.date <= b)]
    cnt = sel.groupby('date').size()
    w = []
    for it in range(300):
        s = [P[ds & (P.date == d)].sample(min(k, (ds & (P.date == d)).sum()), random_state=int(rng.integers(1e9))) for d, k in cnt.items()]
        w.append(pd.concat(s).W5.mean())
    print(per, 'scelta W5', round(sel.W5.mean(), 3), 'caso: mediana', round(np.median(w), 3), '95°', round(np.percentile(w, 95), 3),
          'quota estrazioni sotto', round(np.mean(np.array(w) < sel.W5.mean()), 3))
# regioni e anni, per la regola scelta e per R1 (crescita forte e qualita', PEG alto) del tune_05
med = F.groupby('date').f12.transform('median')
for reg in ['USA', 'Europa', 'Asia', 'Altri']:
    X = F[m & (F.reg == reg) & F.f12.notna()]
    print('scelta', reg, 'n/data', round(len(X) / 56, 1), 'W5', round(X.W5.mean(), 3), 'L20', round(X.L20.mean(), 3))
r, n = run(F, m)
for per, (a, b) in PERIODS.items(): print('portafoglio radar (solo informativo)', per, round(cagr(r, a, b), 3), 'universo', round(cagr(ru, a, b), 3))
pd.to_pickle({'best': best}, f'{BASE}/res/tune_radar_best.pkl')
# ultimi nomi del radar (30/09/2026) a titolo di esempio
last = F[m & (F.date == F.date.max())][['name', 'reg', 'revq', 'rev_cagr', 'hi52', 'peg', 'roe', 'mcap_usd']].sort_values('revq', ascending=False)
print(len(last)); print(last.head(40).round(2).to_string())
last.to_csv(f'{BASE}/res/tune_radar_ultimo.csv', index=False)
