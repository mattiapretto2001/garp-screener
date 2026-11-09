# avv_reg_02: "anni di storia dei bilanci" (hist_y) e' eta' vera o profondita' dell'archivio EODHD?
# (a) distribuzione e troncamento per regione; (b) uscite dal listino a parita' di eta' dalla quotazione (solo dove age_y c'e');
# (c) effetto per decili: e' tutto nelle societa' giovani (IPO recenti)?; (d) FM con hist_y spezzata in "giovane <5a" e resto.
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
warnings.filterwarnings('ignore')
pd.set_option('display.width', 250)
F = fv3.load(cols=['t', 'date', 'reg', 'reg_rob', 'hist_y', 'age_y', 'delisted', 'fwd12_eur', 'rk12_reg', 'bot20_reg', 'top5_reg', 'crash50',
                   'delist12', 'bankrupt12', 'mcap_usd', 'n_years', 'sector_n', 'vol1y'])
F = F[F.fwd12_eur.notna()].copy()
F['first_year'] = (F.date - pd.to_timedelta(F.hist_y * 365.25, 'D')).dt.year
print('(a) anno del primo bilancio annuale in EODHD, per regione (quantili sulle societa)')
fy = F.groupby('t').agg(first_year=('first_year', 'min'), reg=('reg', 'first'), delisted=('delisted', 'first'))
print(fy.groupby('reg').first_year.describe(percentiles=[.05, .25, .5, .75, .95]).round(0).to_string())
print('quota societa con primo bilancio <=1990 / <=1995 / <=2000 per regione:')
print(fy.groupby('reg').first_year.apply(lambda s: pd.Series({'<=1990': (s <= 1990).mean(), '<=1995': (s <= 1995).mean(), '<=2000': (s <= 2000).mean()})).unstack().round(2).to_string())
print('\nanno del primo bilancio: uscite vs attive (societa)')
print(fy.groupby(['reg', 'delisted']).first_year.describe(percentiles=[.25, .5, .75]).round(0).to_string())
# (b) USA con data IPO: profondita' storia vs eta' dalla quotazione, uscite vs attive
U = F[(F.reg == 'USA') & F.age_y.notna()].copy()
U['gap'] = U.hist_y - U.age_y
U['age_bin'] = pd.cut(U.age_y, [0, 3, 6, 10, 15, 20, 30, 100])
print('\n(b) USA: hist_y - age_y (anni di bilanci prima della quotazione, negativo = archivio piu corto della quotazione), mediana')
print(U.groupby(['age_bin', 'delisted']).gap.median().unstack().round(2).to_string())
print('quota righe con hist_y < age_y - 2 (archivio che parte molto dopo la quotazione):')
print(U.assign(short=U.gap < -2).groupby(['age_bin', 'delisted']).short.mean().unstack().round(3).to_string())
# fuori dagli USA: age_y?
print('\ncopertura age_y per regione:', F.groupby('reg').age_y.apply(lambda s: s.notna().mean()).round(2).to_dict())
# (c) decili di hist_y (per data x regione) -> rango medio, disastri, uscite/fallimenti a 12 mesi
F['dq'] = F.groupby(['date', 'reg']).hist_y.transform(lambda s: pd.qcut(s.rank(method='first'), 10, labels=False) + 1)
T = F.groupby('dq').agg(hist_med=('hist_y', 'median'), rango=('rk12_reg', 'mean'), bot20=('bot20_reg', 'mean'), top5=('top5_reg', 'mean'),
                        crash=('crash50', 'mean'), delist12=('delist12', 'mean'), fall12=('bankrupt12', 'mean'), vol=('vol1y', 'median'),
                        mcap_med=('mcap_usd', lambda s: s.median() / 1e9))
print('\n(c) decili di hist_y (tutto il campione)'); print(T.round(3).to_string())
for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia']:
    S = F[F.reg_rob == rg]
    q = S.groupby('date').hist_y.transform(lambda s: pd.qcut(s.rank(method='first'), 5, labels=False) + 1)
    print(rg, 'quintili hist_y -> rango medio:', S.groupby(q).rk12_reg.mean().round(3).tolist(), ' hist mediana:', S.groupby(q).hist_y.median().round(1).tolist())
# (d) FM: hist_y vs dummy "giovane" (<5 anni) e hist_y troncata a 15 anni
M = rc.load(); M = M[M.fwd12_eur.notna()].reset_index(drop=True)
H = fv3.load(cols=['hist_y', 'fwd12_eur'])
H = H[H.fwd12_eur.notna()].reset_index(drop=True)
M['hist_raw'] = H.hist_y.values
M['y_rk'] = (M.rk12_reg - 0.5) * rc.S12; M['bot20'] = M.bot20_reg.astype(float) * 100
G = rc.GLOBAL; ZG = ['z_' + c for c in G]
M['young5'] = (M.hist_raw < 5).astype(float)
M['young8'] = (M.hist_raw < 8).astype(float)
M['h_cap15'] = M.hist_raw.clip(upper=15)
M['z_hcap15'] = rc.rank_z(M, ['h_cap15'], ['date', 'reg'])['h_cap15']
M['z_hold'] = rc.rank_z(M.assign(h=M.hist_raw.where(M.hist_raw >= 8)), ['h'], ['date', 'reg'])['h']   # solo fra le "vecchie"
print('\nquota righe con hist_y <5 anni: %.3f, <8 anni: %.3f' % (M.young5.mean(), M.young8.mean()))
X0 = [c for c in ZG if c != 'z_hist_y']
for nm, extra in [('hist_y sostituita da dummy <5a', ['young5']), ('dummy <8a', ['young8']), ('dummy <5a + rango hist_y', ['young5', 'z_hist_y']),
                  ('hist_y troncata a 15a', ['z_hcap15']), ('dummy <8a + rango fra le >=8a', ['young8', 'z_hold'])]:
    for y in ['y_rk', 'bot20']:
        C = rc.fm(M[['date'] + X0 + extra + [y]].assign(z_hold=M.z_hold.fillna(0)) if 'z_hold' in extra else M[['date'] + X0 + extra + [y]], X0 + extra, y)
        print('%-32s %-6s ' % (nm, y) + ' | '.join('%s coef %.3f t %.1f' % (e, C[e].mean(), fv3.nw_t(C[e])) for e in extra))
