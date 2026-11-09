# tune_11 (07/11): core e GARP attuale per fascia di capitalizzazione alla data (mondo e USA), contro l'universo della stessa fascia.
import pandas as pd, numpy as np
from tune_common import run, cagr, tstat, mask, BASE_P, PERIODS, BASE
F = pd.read_pickle(f'{BASE}/res/panel2.pkl').reset_index(drop=True)
REB = sorted(F.date.unique()); UNI = ~F.excl_sector
A = mask(F, BASE_P); CORE = mask(F, dict(BASE_P, revq=0.20)) & (F.hi52 >= 0.8).fillna(False)
PALL = {**PERIODS, '2012-26': ('2011-12-31', '2026-09-30')}
rows = []
for reg, R in [('Mondo', UNI), ('USA', UNI & (F.reg == 'USA')), ('Fuori USA', UNI & (F.reg != 'USA'))]:
    for sz, S in [('0,3-2 Mld$', F.mcap_usd < 2e9), ('2-10 Mld$', F.mcap_usd.between(2e9, 10e9)), ('>10 Mld$', F.mcap_usd > 10e9), ('>=2 Mld$', F.mcap_usd >= 2e9)]:
        u = pd.Series({t: F.loc[R & S & (F.date == t), 'r_eur'].mean() for t in REB})
        for nm, m in [('GARP attuale', A), ('Core', CORE)]:
            r, n = run(F, m & R & S)
            for p, (a, b) in PALL.items():
                ds = [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
                rows.append(dict(regione=reg, fascia=sz, variante=nm, periodo=p, n=n[ds].mean(), cagr=cagr(r, a, b), univ=cagr(u, a, b),
                                 diff=cagr(r, a, b) - cagr(u, a, b), t=tstat((r - u)[ds])))
T = pd.DataFrame(rows); T.to_csv(f'{BASE}/res/v11_dimensione.csv', index=False)
pd.set_option('display.width', 250)
print(T.pivot_table(index=['regione', 'fascia', 'variante'], columns='periodo', values=['n', 'cagr', 'diff', 't'], sort=False).round(3).to_string())
# quota di promossi del GARP attuale sotto 2 Mld$ nel 2025-26
x = F[A & UNI & (F.per == '2025-26')]; print('quota GARP attuale <2 Mld$ 2025-26', round((x.mcap_usd < 2e9).mean(), 2))
