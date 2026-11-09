# pp_05: robustezza sul periodo pulito: senza gli anni 2020 e 2025, senza i 10 titoli che hanno contribuito di piu',
# Europa solo dal 2020 (prima EODHD non ha quasi uscite europee), costo 1% invece di 0,5%, rotazione annua.
from pp_common import *
import tune_common
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
D = pd.Series(REB, index=REB)
NOT2025 = [d for d in CLEAN if not (pd.Timestamp('2019-12-31') <= d <= pd.Timestamp('2020-09-30')) and not (pd.Timestamp('2024-12-31') <= d <= pd.Timestamp('2025-09-30'))]


def ann(r, ds):
    return (1 + r[ds]).prod() ** (4 / len(ds)) - 1        # annualizzato su trimestri (approssimazione)


rows = []
names = list(LISTS) + ['50% core + 50% Q3']
for name in names:
    if name == '50% core + 50% Q3':
        rc, _ = run(F, CORE & UNI); rq, _ = run(F, Q3 & QU & B5); r = 0.5 * rc + 0.5 * rq; u = useries(QU); m = (CORE & UNI) | (Q3 & QU & B5); univ = QU
    else:
        m0, univ = LISTS[name]; m = m0 & univ; r, n = run(F, m); u = useries(univ)
    base = cagr(r, *PP['2018-26']) - cagr(u, *PP['2018-26'])
    no2 = ann(r, NOT2025) - ann(u, NOT2025)
    # contributo di ogni titolo nel periodo pulito: somma di r_eur / numero di titoli della data
    X = F[m & F.date.isin(CLEAN)]
    contrib = (X.r_eur / X.groupby('date').t.transform('size')).groupby(X.t).sum().sort_values(ascending=False)
    top10 = list(contrib.index[:10])
    if name == '50% core + 50% Q3':
        rc2, _ = run(F, CORE & UNI & ~F.t.isin(top10)); rq2, _ = run(F, Q3 & QU & B5 & ~F.t.isin(top10)); r2 = 0.5 * rc2 + 0.5 * rq2
    else:
        r2, _ = run(F, m & ~F.t.isin(top10))
    no10 = cagr(r2, *PP['2018-26']) - cagr(u, *PP['2018-26'])
    # costo 1%
    tune_common.COST = 0.01
    if name == '50% core + 50% Q3':
        a1, _ = tune_common.run(F, CORE & UNI); b1, _ = tune_common.run(F, Q3 & QU & B5); r1 = 0.5 * a1 + 0.5 * b1
    else:
        r1, _ = tune_common.run(F, m)
    tune_common.COST = 0.005
    c1 = cagr(r1, *PP['2018-26']) - cagr(u, *PP['2018-26'])
    # rotazione: quota del portafoglio cambiata in un anno (vendite + acquisti)/2, dalla differenza di costo
    turn = ((r - r1)[CLEAN].mean() / 0.005) * 4 / 2
    rows.append(dict(lista=name, diff_2018_26=base, senza_2020_2025=no2, senza_top10=no10, costo_1pct=c1, rotazione_annua=turn,
                     t_senza_2020_2025=nw((r - u)[NOT2025]), top10=', '.join(t.split('.')[0] for t in top10)))
    print(name, flush=True)
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/pp_05_robustezza.csv', index=False)
print(T.drop(columns='top10').round(3).to_string()); print(T[['lista', 'top10']].to_string())

# Europa dal 2020 (date dal 31/12/2019) e USA grandi dal 2018: confronto
rows = []
EU20 = ('2019-12-31', '2026-09-30')
for name, (m0, univ) in LISTS.items():
    if name.startswith('Top 30'): continue
    for reg in ['Europa', 'USA grandi', 'Asia']:
        R = REG[reg]; r, n = run(F, m0 & univ & R); u = useries(univ & R)
        ds = [d for d in REB if pd.Timestamp(EU20[0]) <= d <= pd.Timestamp(EU20[1])]
        rows.append(dict(lista=name, regione=reg, diff_2018_26=cagr(r, *PP['2018-26']) - cagr(u, *PP['2018-26']),
                         diff_2020_26=cagr(r, *EU20) - cagr(u, *EU20), t_2020_26=nw((r - u)[ds]), n=n.reindex(ds).mean()))
E = pd.DataFrame(rows); E.to_csv(f'{OUT}/pp_05_europa2020.csv', index=False)
print(E.round(3).to_string())
