# temi_06: test (b). Dentro le industrie segnalate, quali variabili di societa' scelgono i vincitori?
# Insieme "tema" = industria segnalata da B oppure da MOM alla data (circa 17 industrie, 400 societa' per data).
# Misura: correlazione di rango DENTRO l'industria (variabile e esito ordinati nell'industria alla data), media per data, t NW 4.
# Confronto: stessa misura nelle industrie NON segnalate (la differenza dice se l'effetto e' specifico dei temi).
from temi_common import *
V = pd.read_pickle(f'{OUT}/ind_flags2.pkl')
CI = pd.read_pickle(f'{OUT}/comp_ind.pkl')
VARS = ['rel_mom_ind', 'rel_revg_ind', 'logmcap', 'roic', 'fcf_m', 'opm_avg5', 'n_loss_5y', 'hi52', 'vol1y', 'mom12_1', 'ev_sales',
        'fcfy', 'dsh3', 'revq', 'rev_cagr', 'accel_q']
Fc = fv3.load(cols=['t', 'date', 'reg_rob', 'fwd12_eur', 'rk12_reg', 'top5_reg', 'bot20_reg', 'crash50', 'mcap_usd'] + VARS)
C = CI.merge(Fc, on=['t', 'date']).merge(V[['ind', 'date', 'B', 'MOM', 'BM']], on=['ind', 'date'], how='inner')
C['tema'] = C.B | C.MOM
C = C[C.fwd12_eur.notna()].copy()
def within_ic(X, var, tgt):
    X = X[X[var].notna() & X[tgt].notna()]
    g = X.groupby(['date', 'ind'])
    n = g[var].transform('count')
    rv = (g[var].rank() - 0.5) / n - 0.5; ry = (g[tgt].rank() - 0.5) / n - 0.5      # ranghi centrati in 0 in ogni industria
    Z = pd.DataFrame({'d': X.date, 'v': rv, 'y': ry})[n >= 3]
    # correlazione per data (somme dentro industrie, gia' centrate)
    s = Z.groupby('d').apply(lambda z: (z.v * z.y).sum() / np.sqrt((z.v ** 2).sum() * (z.y ** 2).sum()) if len(z) > 30 else np.nan)
    return s.dropna()
rows = []
for var in VARS:
    for tgt in ['rk12_reg', 'top5_reg', 'bot20_reg']:
        a = within_ic(C[C.tema], var, tgt); b = within_ic(C[~C.tema], var, tgt)
        dd = (a - b).dropna()
        o = {'var': var, 'target': tgt, 'IC_temi': a.mean(), 't_temi': nw_t(a), 'IC_altre': b.mean(), 't_altre': nw_t(b),
             'diff': dd.mean(), 't_diff': nw_t(dd)}
        for p in PER3:
            s = a[[per3_of(x) == p for x in a.index]]; o['IC_' + p] = s.mean()
        o['segni_uguali'] = int(np.sign(o['IC_2012-16']) == np.sign(o['IC_2017-21']) == np.sign(o['IC_2022-26']))
        rows.append(o)
R = pd.DataFrame(rows)
R['p_holm'] = holm([tp(t) for t in R.t_temi]); R['p_holm_diff'] = holm([tp(t) for t in R.t_diff])
pd.set_option('display.width', 250)
print(R.round(3).to_string()); R.to_csv(f'{OUT}/b_dentro_temi.csv', index=False)
# quintili dentro l'industria, solo temi: eccesso medio vs industria (pp a 12 mesi) per le variabili piu' forti
C['xs_ind'] = C.fwd12_eur - C.groupby(['date', 'ind']).fwd12_eur.transform('mean')
T = C[C.tema]
print('\nquintili dentro industria (solo temi): eccesso a 12 mesi vs propria industria, pp; quota top5; quota bot20')
for var in ['rel_mom_ind', 'hi52', 'vol1y', 'fcf_m', 'logmcap', 'dsh3', 'ev_sales', 'roic', 'rel_revg_ind']:
    q = T.groupby(['date', 'ind'])[var].rank(pct=True)
    qq = pd.cut(q, [0, .2, .4, .6, .8, 1.0], labels=[1, 2, 3, 4, 5])
    G = T.assign(q=qq).groupby('q', observed=True).agg(ecc=('xs_ind', 'mean'), top5=('top5_reg', 'mean'), bot20=('bot20_reg', 'mean'), crash=('crash50', 'mean'))
    print(var, ' | '.join(f"Q{i}: {100*r.ecc:+.1f} / {100*r.top5:.1f}% / {100*r.bot20:.0f}% / {100*r.crash:.1f}%" for i, r in G.iterrows()))
# per regione: IC (rk12_reg) delle 5 variabili principali dentro i temi
print()
for var in ['rel_mom_ind', 'hi52', 'vol1y', 'fcf_m', 'logmcap', 'dsh3']:
    print(var, {rg: round(within_ic(T[T.reg_rob == rg], var, 'rk12_reg').mean(), 3) for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia']})
