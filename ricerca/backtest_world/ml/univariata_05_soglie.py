# univariata_05: le poche soglie che hanno senso (sopravvivenza): autonomia di cassa, diluizione, distanza dal massimo,
# fra TUTTE le societa' e fra le non profittevoli. Media per data, poi media delle date (e per periodo).
import numpy as np, pandas as pd
from univariata_common import *
F = load_dev()
F['nonprof'] = F.ni_ttm <= 0
F['b_runway'] = pd.cut(np.where(F.burner == 1, F.runway_y, 99), [-1, 1, 2, 3, 5, 10.01, 100],
                       labels=['brucia, <1 anno', 'brucia, 1-2', 'brucia, 2-3', 'brucia, 3-5', 'brucia, 5+', 'non brucia'])
F['b_dsh1'] = pd.cut(F.dsh1, [-9, -0.01, 0.02, 0.05, 0.10, 0.25, 9], labels=['<-1%', '-1/+2%', '+2/5%', '+5/10%', '+10/25%', '>25%'])
F['b_hi52'] = pd.cut(F.hi52, [0, 0.4, 0.6, 0.75, 0.9, 1.01], labels=['<40%', '40-60%', '60-75%', '75-90%', '>=90%'])
F['b_cash'] = pd.cut(F.cash_mcap, [-1, 0.05, 0.15, 0.3, 0.5, 99], labels=['<5%', '5-15%', '15-30%', '30-50%', '>=50%'])
pd.set_option('display.width', 250)
out = []
for pop, m in [('tutte', F.rk12_reg.notna()), ('non profittevoli', F.nonprof)]:
    for b in ['b_runway', 'b_dsh1', 'b_hi52', 'b_cash']:
        X = F[m & F[b].notna()]
        g = X.groupby(['date', b], observed=True).agg(n=('rk12_reg', 'size'), rk=('rk12_reg', 'mean'), top5=('top5_reg', 'mean'),
                                                     bot20=('bot20_reg', 'mean'), crash=('crash50', 'mean'), per=('per3', 'first')).reset_index()
        g = g[g.n >= 5]
        a = g.groupby(b, observed=True).agg(righe_per_data=('n', 'mean'), rk=('rk', 'mean'), top5=('top5', 'mean'), bot20=('bot20', 'mean'),
                                            crash=('crash', 'mean'))
        for p in PERS:
            a[f'crash_{p}'] = g[g.per == p].groupby(b, observed=True).crash.mean()
            a[f'bot20_{p}'] = g[g.per == p].groupby(b, observed=True).bot20.mean()
        a.insert(0, 'pop', pop); a.insert(1, 'var', b); a.index.name = 'fascia'
        out.append(a.reset_index())
        print('\n==', pop, b); print(a.round(3).to_string())
pd.concat(out).to_csv(f'{OUT}/soglie_sopravvivenza.csv', index=False)
