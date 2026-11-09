# avv_temi_05: panieri B / MOM / BM con la funzione dell'autore; effetto del trimestre parziale finale (30/09/2026 -> 06/11/2026),
# CAGR senza il 2025-26, numero di titoli, quota sotto 2 Mld$, t vs universo.
from avv_temi_common import *
from temi_common import portfolio, cagr, maxdd
C = pd.read_pickle(f'{OUT}/C.pkl')
out = {}
for r in ['B', 'MOM', 'BM', 'CALDE', 'UNIV']:
    sel = C[r] if r != 'UNIV' else pd.Series(True, index=C.index)
    out[r] = portfolio(C, sel)
U = out['UNIV'][0]
for r, (q, tv) in out.items():
    d = q.index; q2 = q[d < '2026-09-30']; q3 = q[d < '2024-12-31']
    n = C[C[r]].groupby('date').size().mean() if r != 'UNIV' else C.groupby('date').size().mean()
    small = (C[C[r]].mcap_usd < 2e9).mean() if r != 'UNIV' else (C.mcap_usd < 2e9).mean()
    print(f'{r:5s} CAGR 2012-26 {cagr(q):.3f} | senza trimestre parziale {cagr(q2):.3f} | 2012-24 (senza 2025-26) {cagr(q3):.3f} vs univ {cagr(U[U.index < "2024-12-31"]):.3f}'
          f' | perdita max {maxdd(q):.2f} | rotazione {tv.mean():.2f} | titoli medi {n:.0f} | quota <2 Mld$ {small:.2f}'
          + ('' if r == 'UNIV' else f' | diff t NW1 {nw_t((q - U).values, 1):.2f} | diff t senza 2025-26 {nw_t((q3 - U[U.index < "2024-12-31"]).values, 1):.2f}'))
print('rendimento medio del trimestre parziale finale (univ):', round(float(U.iloc[-1]), 4), U.index[-1].date())
