# tune_04b: margine lordo e sua tendenza. I bilanci EODHD compatti non hanno l'utile lordo, quindi uso i dati SEC (USA,
# societa' quotate oggi, cap >= 300 M$, da backtest_svolta2/cache). Attenzione: niente societa' uscite dal listino.
import json, pandas as pd, numpy as np
from tune_common import tstat, PERIODS, period_of
C = '${RICERCA_BASE}/backtest_svolta2/cache'
F = pd.read_pickle(f'{C}/features.pkl')
RQ = pd.read_pickle(f'{C}/rq.pkl')
U = pd.read_csv(f'{C}/universe.csv'); S = json.load(open(f'{C}/sic.json'))
sic = {r.ticker: int(S.get(str(r.cik), ['0'])[0] or 0) for r in U.itertuples()}
F['sic'] = F.ticker.map(sic).fillna(0)
bad = F.sic.between(6000, 6799) | F.sic.between(4900, 4999) | F.sic.between(1000, 1499) | F.sic.between(2900, 2999)
F['mcap'] = F.price * F.sh
F = F[~bad & (F.mcap >= 3e8) & (F.rev_ttm > 0)].copy()
D = list(RQ.index)
f12 = {}
for i, t in enumerate(D):
    if i + 4 > len(D) - 1: continue
    f12[t] = (1 + RQ.iloc[i:i + 4].fillna(0)).prod() - 1
F['f12'] = [f12[d].get(k, np.nan) if d in f12 else np.nan for d, k in zip(F.date, F.ticker)]
F = F[F.f12.notna()]
F['W5'] = F.groupby('date').f12.rank(pct=True) >= 0.95
F['gm'] = F.gm_ttm; F['d_gm'] = F.gm_ttm - F.gm_ttm4
F['revq'] = F.yoy0.clip(-1, 10); F['roe'] = F.ni_ttm / F.equity.where(F.equity > 0)
F['de'] = F.debt / F.equity.where(F.equity > 0); F['fcfy'] = F.fcf_ttm / F.mcap
F['epsg'] = np.where(F.eps_ttm4 > 0, F.eps_ttm / F.eps_ttm4 - 1, np.nan)
F['pe'] = F.mcap / F.ni_ttm.where(F.ni_ttm > 0); F['peg'] = F.pe / (F.epsg * 100)
F['per'] = F.date.map(period_of)
F['GARP'] = ((F.roe > .15) & (F.de < 1) & (F.fcf_ttm > 0) & (F.revq > .05) & (F.rev_cagr > .1) & (F.peg > 0) & (F.peg < 2)).fillna(False)
CTRL = {'peg': -1, 'revq': 1, 'rev_cagr': 1, 'roe': 1, 'fcfy': 1, 'de': -1}
def prank(s): return ((s.rank() - 0.5) / s.notna().sum()).fillna(0.5)
out = []
for col in ['gm', 'd_gm']:
    for g, X in [('tutto', F)] + [(p, F[F.per == p]) for p in PERIODS]:
        co = []
        for t, x in X.groupby('date'):
            Z = np.column_stack([np.ones(len(x))] + [prank(x[c] * s).values for c, s in CTRL.items()] + [prank(x[col]).values])
            co.append(np.linalg.lstsq(Z, x.f12.rank(pct=True).values, rcond=None)[0][-1])
        q = X.groupby('date')[col].rank(pct=True)
        G = X[X.GARP]; qg = G.groupby('date')[col].rank(pct=True)
        out.append(dict(segnale=col, gruppo=g, coef=np.mean(co), t=tstat(co) / 2, W5_alto=X[q > .8].W5.mean(), W5_basso=X[q <= .2].W5.mean(),
                        garp_f12_alto=G[qg > .5].f12.median(), garp_f12_basso=G[qg <= .5].f12.median(), n=len(X)))
T = pd.DataFrame(out); print(T.round(3).to_string()); T.to_csv('res/tune_margine_lordo_usa.csv', index=False)
