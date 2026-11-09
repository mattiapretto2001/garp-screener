# avv_temi_06: quanto pesa un solo trimestre? Contributo della data migliore e del trimestre 31/03-30/06/2026 (rally dei semiconduttori)
from avv_temi_common import *
C = pd.read_pickle(f'{OUT}/C.pkl')
for r in ['B', 'MOM', 'BM']:
    d, m, t = spread(C, r, 'xs3', 1)
    top = d.sort_values(ascending=False)
    d2 = d.drop(pd.Timestamp('2026-03-31')); d3 = d.drop(top.index[:3])
    print(f'{r:4s} 3m base {m:+.2f} (t {t:.2f}) | 2026-03-31 da sola {100*d.loc["2026-03-31"]:+.1f} pp | senza quella data {100*d2.mean():+.2f} (t {nw_t(d2,1):.2f})'
          f' | senza le 3 date migliori ({", ".join(str(x.date()) for x in top.index[:3])}) {100*d3.mean():+.2f} (t {nw_t(d3,1):.2f})')
    d12, m12, t12 = spread(C, r, 'xs12_reg', 4)
    k = d12[d12.index <= '2025-03-31']
    print(f'      12m base {m12:+.2f} (t {t12:.2f}) | senza le date con il trimestre Q2-2026 nella finestra {100*k.mean():+.2f} (t {nw_t(k,4):.2f})'
          f' | 2022-26 base {100*d12[d12.index>"2021-09-30"].mean():+.2f} -> {100*k[k.index>"2021-09-30"].mean():+.2f} (t {nw_t(k[k.index>"2021-09-30"],4):.2f})')
# quota di date con segno positivo a 3 mesi e test dei segni
for r in ['B', 'MOM', 'BM']:
    d, _, _ = spread(C, r, 'xs3', 1); print(r, '3m date positive %d/%d' % ((d > 0).sum(), len(d)), 'mediana %.2f pp' % (100 * d.median()))
