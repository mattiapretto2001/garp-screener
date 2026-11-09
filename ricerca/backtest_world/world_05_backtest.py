# Fase 5: filtri GARP, varianti, ribilanciamento trimestrale, costi 0,5% per operazione, EUR e valuta locale.
import pickle, pandas as pd, numpy as np
from world_common import *
TODAY = pd.Timestamp('2026-11-06')
F = pd.read_pickle(f'{BASE}/res/feat_raw.pkl')
M = pd.read_pickle(f'{BASE}/res/meta.pkl').set_index('t')
RQ = pd.read_pickle(f'{BASE}/res/rq.pkl')
FX = pd.read_pickle(f'{BASE}/eod/fx.pkl').sort_index().ffill()
B = pickle.load(open(f'{BASE}/eod/bench.pkl', 'rb'))
REB = sorted(F.date.unique())
NEXT = {t: (REB[i + 1] if i + 1 < len(REB) else TODAY) for i, t in enumerate(REB)}
COST = 0.005
EXCL_S = {'Financial Services', 'Financial', 'Financials', 'Basic Materials', 'Materials', 'Energy', 'Utilities', 'Real Estate',
          'Capital Markets', 'Diversified Financial Services', 'Electric Utilities', 'Energy Equipment & Services',
          'Equity Real Estate Investment Trusts (REITs)', 'Multi-Utilities', 'Regional Banks'}
def fx_at(c, t):
    c = {'GBX': 'GBP', 'GBp': 'GBP', 'ZAC': 'ZAR', 'ILA': 'ILS'}.get(c, c)
    if c not in FX.columns: return np.nan
    i = FX.index.searchsorted(t, side='right') - 1; return FX[c].iloc[max(i, 0)]
# ------------------------------------------------------------------ metriche
F['cur'] = F.cur.replace('', np.nan)
F = F.join(M[['ex', 'region', 'sector', 'cur_px', 'delisted', 'name', 'country']], on='t')
F['cur_rep'] = F.cur.where(F.cur.notna(), F.cur_px.replace({'GBX': 'GBP', 'GBp': 'GBP'}))
fxc = {}
for (c, t), _ in F.groupby(['cur_px', 'date']): fxc[(c, t)] = fx_at(c, t)
for (c, t), _ in F.groupby(['cur_rep', 'date']): fxc[(c, t)] = fx_at(c, t)
F['fx_px'] = [fxc.get((c, t), np.nan) for c, t in zip(F.cur_px, F.date)]
F['fx_rep'] = [fxc.get((c, t), np.nan) for c, t in zip(F.cur_rep, F.date)]
F['mcap_usd'] = F.sh * F.px * F.fx_px
F.loc[(F.mcap_usd > 6e12) | (F.mcap_usd < 1e6), 'mcap_usd'] = np.nan
F['mcap'] = F.mcap_usd / F.fx_rep            # in valuta di bilancio
shr = F.sh0 / F.sh4; okS = shr.between(0.67, 1.5)
adj = np.where(okS, F.sh4 / F.sh0, 1.0)       # correzione per azioni emesse/riacquistate
F['epsg'] = np.where(F.ni_ttm4 > 0, F.ni_ttm / F.ni_ttm4 * adj - 1, np.nan)
F['epsq'] = np.where(F.ni_qp > 0, F.ni_q / F.ni_qp * adj - 1, np.nan)
F['revq'] = np.where(F.rev_qp > 0, F.rev_q / F.rev_qp - 1, np.nan)
F['pe'] = F.mcap / F.ni_ttm
F['peg'] = F.pe / (F.epsg * 100)
F['roe'] = F.ni_ttm / F.equity
F['de'] = F.debt / F.equity
F['fcfy'] = F.fcf_ttm / F.mcap
F = F.replace([np.inf, -np.inf], np.nan)
R = RQ.set_index(['t', 'date'])
F = F.join(R, on=['t', 'date'])
F = F[F.r.notna()]
# rendimento in EUR: cambio valuta del titolo / EUR tra inizio e fine trimestre
cur_e = {}
for c in F.cur_px.dropna().unique():
    for t in REB:
        a = fx_at(c, t) / fx_at('EUR', t); b = fx_at(c, NEXT[t]) / fx_at('EUR', NEXT[t]); cur_e[(c, t)] = b / a - 1
F['r_eur'] = (1 + F.r) * (1 + np.array([cur_e.get((c, t), np.nan) for c, t in zip(F.cur_px, F.date)])) - 1
sec_ok = ~F.sector.isin(EXCL_S)
LQ = pd.read_pickle(f'{BASE}/res/liq_pit.pkl').set_index(['t', 'date']).liq
F['liq'] = LQ.reindex(pd.MultiIndex.from_arrays([F.t, F.date])).fillna(False).values
HOMEOK = pd.Series([(c in HOME[e]) if HOME[e] else True for c, e in zip(F.country, F.ex)], index=F.index)
sec_ok = sec_ok & ~F.name.fillna('').str.contains(r'\bCDR\b') & (HOMEOK | F.country.isna())
F['U'] = (sec_ok & F.liq & (F.mcap_usd >= 300e6) & (F.rev_ttm > 0)).fillna(False)
F['sec_missing'] = F.sector.isna()
COMMON = (F.U & (F.ni_ttm > 0) & (F.epsg > 0) & (F.peg > 0) & (F.equity > 0) & (F.roe > 0.15) & (F.de < 1) & (F.fcf_ttm > 0) &
          (F.revq > 0.05) & (F.epsq > 0.05) & (F.rev_cagr > 0.10)).fillna(False)
F['P1'] = COMMON & (F.peg < 1); F['P2'] = COMMON & (F.peg < 2)
F.to_pickle(f'{BASE}/res/feat.pkl')
def pct(s, higher=True):
    n = s.notna().sum()
    p = (s.rank(method='average') - 0.5) / n if n else s * np.nan
    p = p if higher else 1 - p
    return p.fillna(0.5)
W = {'peg': 30, 'revq': 12, 'epsq': 12, 'rev_cagr': 12, 'roe': 12, 'fcfy': 11, 'de': 11}
LOW = {'peg', 'de'}
def score(mask):
    out = pd.Series(np.nan, index=F.index)
    for t, x in F[mask].groupby('date'):
        out[x.index] = sum(w * pct(x[k], k not in LOW) for k, w in W.items())
    return out
# ------------------------------------------------------------------ motore
def select(mask, topn=None, sc=None):
    S = {}
    d = F[mask]
    if sc is not None: d = d.assign(_s=sc[mask])
    g = dict(list(d.groupby('date')))
    for t in REB:
        x = g.get(t)
        if x is None: S[t] = []; continue
        if topn: x = x.sort_values(['_s', 'mcap_usd'], ascending=[False, False]).head(topn)
        S[t] = list(x.t)
    return S
RL = F.set_index(['date', 't'])[['r', 'r_eur']]
def run(S, col='r_eur'):
    r, n, cost, turn, prev = {}, {}, {}, {}, []
    for t in REB:
        k = S[t]; n[t] = len(k)
        r[t] = RL.loc[[(t, x) for x in k], col].mean() if k else 0.0
        sold = len(set(prev) - set(k)) / len(prev) if prev else (0 if not k else 1)
        bought = len(set(k) - set(prev)) / len(k) if k else 0
        if t == REB[0]: sold, bought = 0, 1   # primo acquisto
        cost[t] = COST * (sold + bought); turn[t] = (sold + bought) / 2; prev = k
    r = pd.Series(r); c = pd.Series(cost)
    return r - c, pd.Series(n), pd.Series(turn), r
PER = {'2012-19': (REB[0], pd.Timestamp('2019-09-30')), '2020-24': (pd.Timestamp('2019-12-31'), pd.Timestamp('2024-09-30')),
       '2025-26': (pd.Timestamp('2024-12-31'), REB[-1]), '2012-26': (REB[0], REB[-1])}
YRS = {'2012-19': range(2012, 2020), '2020-24': range(2020, 2025), '2025-26': range(2025, 2027), '2012-26': range(2012, 2027)}
def yrs(ds): return (NEXT[ds[-1]] - ds[0]).days / 365.25
def cagr(r, ds): return (1 + r[ds]).prod() ** (1 / yrs(ds)) - 1
def maxdd(r): w = (1 + r).cumprod(); return min((w / w.cummax() - 1).min(), 0)
def tstat(x): x = pd.Series(x).dropna(); return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else np.nan
def annual(r):
    y = r.copy(); y.index = [NEXT[t] for t in r.index]
    y.index = pd.to_datetime(y.index); y.index = [d.year if d.month > 1 or d.day > 15 else d.year - 1 for d in y.index]
    return (1 + y).groupby(level=0).prod() - 1
# riferimenti
def bench_q(tk, eur=True):
    d = B[tk].a.astype(float); out = {}
    cur = 'EUR' if tk.endswith('.XETRA') or tk.endswith('.AS') else 'USD'
    for t in REB:
        a0 = d[d.index <= t]; a1 = d[d.index <= NEXT[t]]
        if not len(a0) or (t - a0.index[-1]).days > 10: out[t] = np.nan; continue
        rr = a1.iloc[-1] / a0.iloc[-1] - 1
        if eur and cur == 'USD': rr = (1 + rr) * (fx_at('USD', NEXT[t]) / fx_at('EUR', NEXT[t])) / (fx_at('USD', t) / fx_at('EUR', t)) - 1
        if not eur and cur == 'EUR': rr = (1 + rr) * (fx_at('EUR', NEXT[t]) / fx_at('EUR', t)) - 1
        out[t] = rr
    return pd.Series(out)
vt, vw = bench_q('VT.US'), bench_q('VWCE.XETRA')
WORLD = vw.where(vw.notna(), vt)          # VWCE da quando esiste, prima VT (stesso indice FTSE, in EUR)
SPY = bench_q('SPY.US'); SPY_USD = bench_q('SPY.US', eur=False)
RES, NET, NS, SELS = [], {}, {}, {}
def ev(name, mask_promo, topn=None, univ=None, group='', col='r_eur'):
    univ = F.U if univ is None else univ
    sc = score(mask_promo) if topn else None
    S = select(mask_promo, topn, sc)
    rn, n, tu, rg = run(S, col)
    ur, *_ = run(select(univ), col)
    ur = ur + 0  # l'universo e' un riferimento: niente costi di rotazione
    ur = pd.Series({t: RL.loc[[(t, x) for x in select(univ)[t]], col].mean() for t in REB})
    NET[name] = rn; NS[name] = n; SELS[name] = S
    A = annual(rn); UA = annual(ur); WA = annual(WORLD)
    for p, (a, b) in PER.items():
        ds = [d for d in REB if a <= d <= b]
        yy = [y for y in YRS[p] if y in A.index]
        RES.append(dict(gruppo=group, variante=name, valuta=col, periodo=p, n_medio=n[ds].mean(), trim_vuoti=int((n[ds] == 0).sum()),
                        CAGR=cagr(rn, ds), CAGR_lordo=cagr(rg, ds), vol=rn[ds].std() * 2, maxDD=maxdd(rn[ds]), CAGR_univ=cagr(ur, ds),
                        CAGR_mondo=cagr(WORLD, ds), CAGR_SPY=cagr(SPY if col == 'r_eur' else SPY_USD, ds),
                        anni_sopra_univ=np.mean([A[y] > UA[y] for y in yy]), anni_sopra_mondo=np.mean([A[y] > WA[y] for y in yy]),
                        rotazione=tu[ds].sum() / yrs(ds), t_vs_univ=tstat(rn[ds] - ur[ds]), d_vs_univ=cagr(rn, ds) - cagr(ur, ds)))
    return S, ur
US_ = {}
_, UNIV = ev('V1 PEG<1 lista intera', F.P1, group='mondo')
ev('V2 PEG<2 lista intera', F.P2, group='mondo')
ev('V3 PEG<2 top 30', F.P2, 30, group='mondo')
ev('V4 PEG<1 top 30', F.P1, 30, group='mondo')
for name, P_, n in [('V1 PEG<1 lista intera', F.P1, None), ('V2 PEG<2 lista intera', F.P2, None), ('V3 PEG<2 top 30', F.P2, 30), ('V4 PEG<1 top 30', F.P1, 30)]:
    ev(name + ' (valuta locale)', P_, n, group='locale', col='r')
UR = {}
for reg in ['USA', 'Europa', 'Asia', 'Canada', 'Australia']:
    m = F.region == reg
    _, UR[reg] = ev(f'V3 {reg}', F.P2 & m, 30, univ=F.U & m, group='regioni')
    ev(f'V2 {reg} lista intera', F.P2 & m, None, univ=F.U & m, group='regioni')
    ev(f'V3 {reg} (valuta locale)', F.P2 & m, 30, univ=F.U & m, group='regioni_locale', col='r')
# sopravvivenza: solo societa' ancora quotate oggi
alive = ~F.delisted.astype(bool)
for name, P_, n in [('V1 PEG<1 lista intera', F.P1, None), ('V2 PEG<2 lista intera', F.P2, None), ('V3 PEG<2 top 30', F.P2, 30), ('V4 PEG<1 top 30', F.P1, 30)]:
    ev(name + ' [solo vive]', P_ & alive, n, univ=F.U & alive, group='sopravvissute')
for reg in ['USA', 'Europa', 'Asia']:
    m = F.region == reg
    ev(f'V3 {reg} [solo vive]', F.P2 & m & alive, 30, univ=F.U & m & alive, group='sopravvissute_reg')
# caso: 30 titoli a sorte fra i promossi PEG<2 (500 estrazioni)
rng = np.random.default_rng(11)
S2 = SELS['V2 PEG<2 lista intera']; RND = {p: [] for p in PER}
for it in range(500):
    S = {t: (list(rng.choice(S2[t], 30, replace=False)) if len(S2[t]) > 30 else S2[t]) for t in REB}
    rn, *_ = run(S)
    for p, (a, b) in PER.items():
        ds = [d for d in REB if a <= d <= b]; RND[p].append(cagr(rn, ds))
pickle.dump({'RES': pd.DataFrame(RES), 'NET': NET, 'NS': NS, 'SELS': SELS, 'UNIV': UNIV, 'UR': UR, 'WORLD': WORLD, 'SPY': SPY, 'SPY_USD': SPY_USD,
             'RND': RND}, open(f'{BASE}/res/bt.pkl', 'wb'))
X = pd.DataFrame(RES); X.to_csv(f'{BASE}/res/world_risultati.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
print(X[['variante', 'periodo', 'n_medio', 'trim_vuoti', 'CAGR', 'vol', 'maxDD', 'CAGR_univ', 'CAGR_mondo', 'CAGR_SPY', 'anni_sopra_univ', 'rotazione', 't_vs_univ']].round(3).to_string())
for p in PER: print('caso', p, np.percentile(RND[p], [5, 50, 95]).round(3))
