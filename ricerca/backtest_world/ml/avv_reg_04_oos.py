# avv_reg_04: verifiche sul fuori campione. (1) ricalcolo della correlazione di rango dell'elastic net; senza Asia, senza 2025-26;
# (2) la "guardia anti-disastro" fa piu' della sola volatilita' bassa? confronto per decili con vol1y e con un composito a pesi uguali
# fissato a mano (vol, prezzo/max, storia); (3) il core: quanto pesa una manciata di titoli?
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
warnings.filterwarnings('ignore')
pd.set_option('display.width', 250)
M = rc.load().reset_index(drop=True)
PR = pd.read_pickle(rc.HERE + '/reg_out/enet_pred.pkl')
assert (PR.t.values == M.t.values).all() and (PR.date.values == M.date.values).all()
for k in ['enet_rk', 'enet_b20', 'enet_t5']: M[k] = PR[k].values
F = fv3.load(cols=['vol1y', 'hi52', 'hist_y', 'name'])
M['vol_raw'] = F.vol1y.values; M['name'] = F.name.astype(str).values
for c in ['top5_reg', 'bot20_reg', 'crash50']: M[c] = M[c].astype(float)
E = M[M.enet_rk.notna() & M.rk12_reg.notna()].copy()
def ic(S, k):
    s = pd.Series({d: g[k].rank().corr(g.rk12_reg.rank()) for d, g in S.groupby('date')})
    return s.mean(), fv3.nw_t(s, 4), len(s)
print('(1) IC fuori campione elastic net sul rango')
for nm, S in [('tutti (riproduzione)', E), ('senza Asia', E[E.reg != 'Asia']), ('date <=2023-12', E[E.date <= '2023-12-31']),
              ('senza Asia, date <=2023-12', E[(E.reg != 'Asia') & (E.date <= '2023-12-31')]), ('>=2 Mld$', E[E.mcap_usd >= 2e9])]:
    print('  %-30s IC %.3f t %.2f (n date %d)' % ((nm,) + ic(S, 'enet_rk')))
print('  anti-disastro (-enet_b20) IC sul rango: %.3f t %.2f' % ic(E.assign(ab=-E.enet_b20), 'ab')[:2])
print('  sola volatilita bassa IC sul rango: %.3f t %.2f' % ic(E.assign(lv=-E.vol_raw), 'lv')[:2])
# (2) decili: modello anti-disastro vs sola vol bassa vs composito fisso
E['z_vol'] = E['z_vol1y']; 
E['comp3'] = E[['z_vol1y', 'z_hi52', 'z_hist_y']].fillna(0).mean(1)
E['lowvol'] = -E.vol_raw
E['antid'] = -E.enet_b20
rows = []
for k in ['antid', 'lowvol', 'comp3']:
    dec = E.groupby('date')[k].transform(lambda x: pd.qcut(x.rank(method='first'), 10, labels=False) + 1)
    g = E.groupby(dec)
    T = pd.DataFrame({'rango': g.rk12_reg.mean(), 'rend_medio%': g.fwd12_eur.mean() * 100, 'bot20%': g.bot20_reg.mean() * 100,
                      'crash%': g.crash50.mean() * 100, 'top5%': g.top5_reg.mean() * 100, 'vol_med': g.vol_raw.median()})
    rows.append(T.loc[[1, 5, 9, 10]].assign(punteggio=k))
print('\n(2) decili (1 = peggiore, 10 = piu sicuro), 2015-2025, campione fuori campione')
print(pd.concat(rows).round(3).to_string())
# a parita' di volatilita': dentro i quintili di vol, il modello anti-disastro separa ancora i disastri?
E['vq'] = E.groupby('date').vol_raw.transform(lambda x: pd.qcut(x.rank(method='first'), 5, labels=False) + 1)
E['aq'] = E.groupby(['date', 'vq']).antid.transform(lambda x: pd.qcut(x.rank(method='first'), 5, labels=False) + 1)
print('\ndisastri (bot20 %) per quintile di volatilita (righe) e quintile anti-disastro DENTRO la volatilita (colonne)')
print((E.groupby(['vq', 'aq']).bot20_reg.mean().unstack() * 100).round(1).to_string())
print('rango medio:'); print(E.groupby(['vq', 'aq']).rk12_reg.mean().unstack().round(3).to_string())
# (3) core: contributi dei singoli titoli 2015-2026 (stessa regola di rc.port)
V = M[M.enet_rk.notna() & (M.date <= '2026-06-30')].copy()
dd = sorted(V.date.unique()); uni = V.groupby('date').r_eur.mean()
base = rc.port(V, lambda g: g[g.core], dd); st = rc.pstats(base, uni)
print('\n(3) core 2015-2026: CAGR %.1f%% diff %.1f t %.2f' % (st['CAGR'] * 100, st['diff'] * 100, st['t']))
C = V[V.core]
contrib = (C.r_eur / C.groupby('date').t.transform('count')).groupby(C.t).sum().sort_values(ascending=False)
print('titoli distinti nel core:', C.t.nunique(), '| primi 10 contributi (somma dei rendimenti trimestrali pesati):')
print(', '.join('%s %.2f' % (t, v) for t, v in contrib.head(10).items()))
for k in (1, 3, 5, 10):
    drop = set(contrib.head(k).index)
    P = rc.port(V, lambda g, drop=drop: g[g.core & ~g.t.isin(drop)], dd); s = rc.pstats(P, uni)
    print('  senza i %2d titoli migliori: CAGR %.1f%% diff %+.1f t %.2f | periodi %+.1f / %+.1f / %+.1f' % (k, s['CAGR'] * 100, s['diff'] * 100, s['t'], s['2015-16'] * 100, s['2017-21'] * 100, s['2022-26'] * 100))
# ultimo anno: quanto pesa 2025-26?
P = rc.port(V[V.date <= '2024-12-31'], lambda g: g[g.core], [d for d in dd if d <= pd.Timestamp('2024-12-31')]); s = rc.pstats(P, uni)
print('  core fino a 12/2024: CAGR %.1f%% diff %+.1f t %.2f' % (s['CAGR'] * 100, s['diff'] * 100, s['t']))
