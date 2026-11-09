# scr_06: lista unificata. Un titolo segnalato da 2 o piu' screener e' meglio di uno segnalato da uno solo?
import pandas as pd, numpy as np
from scr_common import *
pd.set_option('display.width', 250)
FL = {'GARP core': CORE, 'GARP top30': TOP30, 'Radar A': RADA, 'Moonshot': M, 'Svolta': SV, 'Qualita Q3': Q3}
for k, v in FL.items(): F['f_' + k] = v.values
F['n_raw'] = sum(v.astype(int) for v in FL.values())                        # core e top30 contati separatamente
F['n_fam'] = (CORE | TOP30).astype(int) + RADA.astype(int) + M.astype(int) + SV.astype(int) + Q3.astype(int)   # famiglie
med = F.groupby('date').f12.transform('median')
F['x12'] = F.f12 - med
rows = []
for cnt in ['n_raw', 'n_fam']:
    for p in list(PERIODS) + ['2012-26']:
        a, b = PALL[p]
        Z = F[(F[cnt] >= 1) & (F.date >= a) & (F.date <= b) & F.f12.notna()]
        for k, z in [('1 segnale', Z[Z[cnt] == 1]), ('2+ segnali', Z[Z[cnt] >= 2]), ('3+ segnali', Z[Z[cnt] >= 3])]:
            rows.append(dict(conteggio=cnt, periodo=p, gruppo=k, righe=len(z), per_data=len(z) / max(1, z.date.nunique()),
                             extra_medio=z.x12.mean(), extra_mediano=z.x12.median(), W5=z.W5.mean(), L20=z.L20.mean(), L50=z.L50.mean()))
T = pd.DataFrame(rows); T.to_csv(f'{BASE}/res/scr_06_unificata.csv', index=False)
print(T.round(3).to_string())
# portafogli
R = []
for cnt in ['n_raw', 'n_fam']:
    for nm, m in [('1 segnale', F[cnt] == 1), ('2+ segnali', F[cnt] >= 2), ('tutti i segnalati', F[cnt] >= 1)]:
        o, r = ev(nm, m, ALL, cnt); R += o
        if nm == '1 segnale': r1 = r
        if nm == '2+ segnali':
            d = r - r1
            for p, (a, b) in PALL.items():
                ds = [x for x in REB if pd.Timestamp(a) <= x <= pd.Timestamp(b)]
                R.append(dict(gruppo=cnt, variante='t (2+ meno 1)', periodo=p, t=tstat(d[ds])))
P = pd.DataFrame(R); P.to_csv(f'{BASE}/res/scr_06_portafogli.csv', index=False)
print(fmt(P[P.variante != 't (2+ meno 1)']).to_string()); print(P[P.variante == 't (2+ meno 1)'][['gruppo', 'periodo', 't']].round(2).to_string())
# quali combinazioni producono i 2+ (famiglie)
Z = F[F.n_fam >= 2]
combo = Z[[c for c in F.columns if c.startswith('f_')]].astype(int).astype(str).agg(''.join, axis=1)
names = [c[2:] for c in F.columns if c.startswith('f_')]
cc = combo.value_counts().head(10)
for k, v in cc.items():
    sel = Z[combo == k]
    print(' + '.join(n for n, b in zip(names, k) if b == '1'), v, 'extra medio', round(sel.x12.mean(), 3), 'W5', round(sel.W5.mean(), 3), 'L20', round(sel.L20.mean(), 3))
# per singolo screener: extra medio quando e' solo vs quando e' in compagnia
for k in FL:
    s = F['f_' + k] & F.f12.notna()
    a1 = F[s & (F.n_fam == 1)]; a2 = F[s & (F.n_fam >= 2)]
    print(f'{k:12s} da solo: n {len(a1):5d} extra {a1.x12.mean():+.3f} W5 {a1.W5.mean():.3f} L20 {a1.L20.mean():.3f} | con altri: n {len(a2):5d} extra {a2.x12.mean():+.3f} W5 {a2.W5.mean():.3f} L20 {a2.L20.mean():.3f}')
print('2+ famiglie all ultima data'); print(F[(F.n_fam >= 2) & (F.date == REB[-1])][['t', 'name'] + ['f_' + k for k in FL]].to_string())
