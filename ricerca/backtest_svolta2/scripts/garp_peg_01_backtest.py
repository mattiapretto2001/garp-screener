# GARP: confronto varianti PEG<1 / PEG<2 / tolleranza EPS / punteggio top N / fasce PEG.
# Riusa le cache point-in-time di svolta_05_features.py (features.pkl, rq.pkl) e le stesse definizioni,
# costi e periodi di svolta_06 / svolta2_09. Uscita: results/garp_peg_*.csv, results/garp_peg_tabelle.md
import pandas as pd, numpy as np, os
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
OUT = f'{BASE}/results'
TODAY = pd.Timestamp('2026-11-03')
F = pd.read_pickle(f'{BASE}/cache/features.pkl')
RQ = pd.read_pickle(f'{BASE}/cache/rq.pkl')
F = F[(F.mcap >= 150e6) & (F.rev_ttm > 0) & F.r3.notna()].copy().reset_index(drop=True)
F['key'] = F.ticker
DATES = sorted(F.date.unique())
PER = {'Calibrazione 2012-19': (pd.Timestamp('2012-01-01'), pd.Timestamp('2019-12-31')),
       'Fuori campione 2020-24': (pd.Timestamp('2020-01-01'), pd.Timestamp('2024-09-30')),
       'Recente 2025-26': (pd.Timestamp('2024-12-31'), pd.Timestamp('2026-09-30'))}
YPER = {'Calibrazione 2012-19': range(2013, 2020), 'Fuori campione 2020-24': range(2020, 2025), 'Recente 2025-26': range(2025, 2027)}
COST_SIDE = 1 / 300 + 0.0035 / 2      # come prima: 0,51% per lato

# ------------------------------------------------------------------ variabili (stesse definizioni di svolta2_09)
sic = F.sic.fillna(0)
garp_sec = ~(sic.between(6000, 6799) | sic.between(4900, 4999) | sic.between(1200, 1399) | sic.between(2900, 2999) | sic.between(4610, 4619) |
             sic.between(1000, 1099) | sic.between(1400, 1499) | sic.between(2600, 2699) | sic.between(2800, 2829) | sic.between(2840, 2899) | sic.between(3300, 3399))
F['epsg'] = F.eps_ttm / F.eps_ttm4 - 1
F['peg'] = (F.mcap / F.ni_ttm) / (F.epsg * 100)
F['roe'] = F.ni_ttm / F.equity
F['de'] = F.debt / F.equity
F['epsq'] = F.eps_q0 / F.eps_q12.where(F.eps_q12 > 0) - 1
F['fcfy'] = F.fcf_ttm / F.mcap
F['ebitda_m'] = F.ebitda_ttm / F.rev_ttm
F['ev'] = F.mcap + F.debt.fillna(0) - F.liq.fillna(0)
F['ebitda_ev'] = (F.ebitda_ttm / F.ev).where(F.ev > 0)
COMMON = (garp_sec & (F.ni_ttm > 0) & (F.epsg > 0) & (F.peg > 0) & (F.equity > 0) & (F.roe > 0.15) & (F.de < 1) &
          (F.fcf_ttm > 0) & (F.yoy0 > 0.05) & (F.rev_cagr > 0.10)).fillna(False)
EPS_STRICT = (F.epsq > 0.05).fillna(False)
EPS_TOL = EPS_STRICT | (F.eps_ttm > F.eps_ttm4).fillna(False)   # proxy della tolleranza (niente stime storiche)
V1 = COMMON & (F.peg < 1) & EPS_STRICT
V2 = COMMON & (F.peg < 2) & EPS_STRICT
V3 = COMMON & (F.peg < 2) & EPS_TOL
V1T = COMMON & (F.peg < 1) & EPS_TOL
V5a = V3 & (F.peg < 1)
V5b = V3 & (F.peg >= 1)
print('tolleranza ridondante? quota promossi V3 non coperti da (eps_ttm>eps_ttm4):',
      (V3 & ~(F.eps_ttm > F.eps_ttm4)).sum(), '/', V3.sum(),
      '| V3 entrati solo per tolleranza:', (V3 & ~EPS_STRICT).sum())

# ------------------------------------------------------------------ punteggio (percentili fra i promossi della stessa data, NaN = 0,5 come lo screener)
PROF = {'ROE': 'roe', 'Margine EBITDA': 'ebitda_m', 'EBITDA/EV': 'ebitda_ev'}
def pct(s, higher=True):
    p = s.rank(pct=True, method='average')
    # come _rank_pct dello screener: (sotto + 0,5 uguali)/n
    n = s.notna().sum(); p = (s.rank(method='average') - 0.5) / n if n else p
    p = p if higher else 1 - p
    return p.fillna(0.5)
def scores(mask, prof, equal=False):
    d = F[mask]
    out = pd.Series(np.nan, index=F.index)
    for t, x in d.groupby('date'):
        comp = {'peg': pct(x.peg, False), 'rev_q': pct(x.yoy0), 'eps_q': pct(x.epsq), 'cagr': pct(x.rev_cagr),
                'fcfy': pct(x.fcfy), 'de': pct(x.de, False), 'prof': pct(x[prof])}
        w = {k: 100 / 7 for k in comp} if equal else dict({k: 70 / 6 for k in comp}, peg=30)
        out[x.index] = sum(w[k] * comp[k] for k in comp)
    return out

# ------------------------------------------------------------------ motore (come svolta2_09)
univ_r = F.groupby('date').r3.mean(); spy_r = F.groupby('date').spy3.first()
def sel(mask, topn=None, sc=None):
    S = {}; d = F[mask].assign(_s=sc[mask] if sc is not None else 0.0)
    g = dict(list(d.groupby('date')))
    for t in DATES:
        x = g.get(t)
        if x is None: S[t] = []; continue
        if topn: x = x.sort_values(['_s', 'mcap'], ascending=[False, False]).head(topn)
        S[t] = list(x.key)
    return S
def run(S):
    r, n, cost, turn, prev = {}, {}, {}, {}, []
    for t in DATES:
        k = S[t]; n[t] = len(k)
        r[t] = RQ.loc[t].reindex(k).fillna(0.0).mean() if k else 0.0
        sold = len(set(prev) - set(k)) / len(prev) if prev else (0 if not k else 1)
        bought = len(set(k) - set(prev)) / len(k) if k else 0
        if t == DATES[0]: sold, bought = 0, 0
        cost[t] = COST_SIDE * (sold + bought); turn[t] = (sold + bought) / 2; prev = k
    return pd.Series(r), pd.Series(n), pd.Series(cost), pd.Series(turn)
def years(ds): return (min(ds[-1] + pd.DateOffset(months=3), TODAY) - ds[0]).days / 365.25
def cagr(r, ds): return (1 + r).prod() ** (1 / years(ds)) - 1
def maxdd(r): w = (1 + r).cumprod(); return min((w / w.cummax() - 1).min(), 0)
def tstat(x):
    x = pd.Series(x).dropna(); return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else np.nan
def annual(r):
    y = r.copy(); y.index = y.index + pd.offsets.QuarterEnd(1)
    return (1 + y).groupby(y.index.year).prod() - 1
UA = annual(univ_r); SA = annual(spy_r)
RES, SER, NET, SEL = [], {}, {}, {}
def ev(name, S, base=None, group=''):
    r, n, c, tu = run(S); SER[name] = r; NET[name] = r - c; SEL[name] = S
    A = annual(r - c)
    for p, (a, b) in PER.items():
        ds = [d for d in DATES if a <= d <= b]
        rr, uu, cc = r[ds], univ_r[ds], c[ds]; rn = rr - cc
        yy = [y for y in YPER[p]]
        row = dict(gruppo=group, variante=name, periodo=p, n_medio=n[ds].mean(), trim_vuoti=int((n[ds] == 0).sum()),
                   CAGR_lordo=cagr(rr, ds), CAGR=cagr(rn, ds), CAGR_univ=cagr(uu, ds), CAGR_SPY=cagr(spy_r[ds], ds),
                   vol=rn.std() * 2, maxDD=maxdd(rn), anni_battuto_univ=(A[yy] > UA[yy]).mean(),
                   trim_battuto_univ=(rn > uu).mean(), turnover_annuo=tu[ds].sum() / years(ds), costo_annuo=cc.sum() / years(ds),
                   t_vs_univ=tstat(rn - uu))
        if base:
            rb = NET[base][ds]; row['d_vs_base'] = row['CAGR'] - cagr(rb, ds); row['t_vs_base'] = tstat(rn - rb)
        RES.append(row)
    ds = DATES
    RES.append(dict(gruppo=group, variante=name, periodo='Tutto 2012-26', n_medio=n.mean(), CAGR_lordo=cagr(r, ds), CAGR=cagr(r - c, ds),
                    CAGR_univ=cagr(univ_r, ds), CAGR_SPY=cagr(spy_r, ds), vol=(r - c).std() * 2, maxDD=maxdd(r - c),
                    anni_battuto_univ=(A[range(2013, 2027)] > UA[range(2013, 2027)]).mean(), trim_battuto_univ=((r - c) > univ_r).mean(),
                    turnover_annuo=tu.sum() / years(ds), costo_annuo=c.sum() / years(ds), t_vs_univ=tstat(r - c - univ_r)))
    return S

ev('G0 GARP storico (lordo, controllo)', sel(V1), group='controllo')
ev('V1 PEG<1, EPS trim. stretto', sel(V1), group='filtri')
ev('V2 PEG<2, EPS trim. stretto', sel(V2), base='V1 PEG<1, EPS trim. stretto', group='filtri')
ev('V3 PEG<2 + tolleranza EPS', sel(V3), base='V2 PEG<2, EPS trim. stretto', group='filtri')
ev('V1t PEG<1 + tolleranza EPS', sel(V1T), base='V1 PEG<1, EPS trim. stretto', group='filtri')
ev('V5a V3 solo PEG<1', sel(V5a), base='V3 PEG<2 + tolleranza EPS', group='fasce')
ev('V5b V3 solo PEG 1-2', sel(V5b), base='V3 PEG<2 + tolleranza EPS', group='fasce')
SC = {}
for pn, pc in PROF.items():
    for eq in (False, True):
        sc = scores(V3, pc, eq); SC[(pn, eq)] = sc
        for N in (15, 30):
            ev(f'V4 top {N} | {pn} | ' + ('pesi uguali' if eq else 'PEG 30'), sel(V3, N, sc), base='V3 PEG<2 + tolleranza EPS', group=f'punteggio{N}')
# ------------------------------------------------------------------ quanto e' caso: N titoli a sorte fra i promossi V3 (1000 estrazioni)
rng = np.random.default_rng(7)
V3S = SEL['V3 PEG<2 + tolleranza EPS']
RND = {}
for N in (15, 30):
    out = {p: [] for p in PER}
    for it in range(1000):
        S = {t: (list(rng.choice(V3S[t], N, replace=False)) if len(V3S[t]) > N else V3S[t]) for t in DATES}
        r, n, c, tu = run(S); rn = r - c
        for p, (a, b) in PER.items():
            ds = [d for d in DATES if a <= d <= b]; out[p].append(cagr(rn[ds], ds))
    RND[N] = {p: np.array(v) for p, v in out.items()}

R = pd.DataFrame(RES); R = R[R.variante != 'G0 GARP storico (lordo, controllo)'].reset_index(drop=True)
R.to_csv(f'{OUT}/garp_peg_risultati.csv', index=False)
SR = pd.DataFrame(NET).assign(universo=univ_r, SPY=spy_r); SR.to_csv(f'{OUT}/garp_peg_serie_nette.csv')
AN = pd.DataFrame({k: annual(v) for k, v in NET.items()}).assign(universo=UA, SPY=SA)
AL = pd.DataFrame({k: annual(v) for k, v in SER.items()})
AN.to_csv(f'{OUT}/garp_peg_annuali_netti.csv'); AL.to_csv(f'{OUT}/garp_peg_annuali_lordi.csv')

# ------------------------------------------------------------------ tabelle markdown
def f(x, d=1): return '' if pd.isna(x) else f'{x * 100:+.{d}f}%'.replace('.', ',').replace('-', '−')
def fp(x): return '' if pd.isna(x) else f'{x * 100:.0f}%'
def fn(x, d=1): return '' if pd.isna(x) else f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
L = []
ctrl = AL['G0 GARP storico (lordo, controllo)']
L.append('## Controllo GARP storico (lordo, anni 2019-2026): ' + ', '.join(f'{y} {ctrl[y]*100:.0f}' for y in range(2019, 2027)))
L.append(f"\nPromossi V3 entrati solo grazie alla tolleranza: {(V3 & ~EPS_STRICT).sum()} su {V3.sum()} posizioni-trimestre; "
         f"V3 senza (EPS TTM > anno prima): {(V3 & ~(F.eps_ttm > F.eps_ttm4)).sum()}")
names = list(dict.fromkeys(R.variante))
for p in list(PER) + ['Tutto 2012-26']:
    L.append(f'\n### {p}\n\n| Variante | Titoli medi | CAGR netto | (lordo) | Volatilità | Max DD | Anni sopra univ. | Rotaz. annua | Δ vs rif. (t) |\n|---|---|---|---|---|---|---|---|---|')
    for nm in names:
        x = R[(R.variante == nm) & (R.periodo == p)].iloc[0]
        dd = f"{f(x.get('d_vs_base'))} ({fn(x.get('t_vs_base'))})" if pd.notna(x.get('d_vs_base', np.nan)) else ''
        L.append(f'| {nm} | {fn(x.n_medio, 0)} | **{f(x.CAGR)}** | {f(x.CAGR_lordo)} | {fp(x.vol)} | {f(x.maxDD, 0)} | {fp(x.anni_battuto_univ)} | {fp(x.turnover_annuo)} | {dd} |')
    x = R[R.periodo == p].iloc[0]
    L.append(f'| Universo | | {f(x.CAGR_univ)} | | | | | | |\n| SPY | | {f(x.CAGR_SPY)} | | | | | | |')
L.append('\n### Anno per anno (netto costi)\n\n| Variante | ' + ' | '.join(str(y) for y in range(2019, 2027)) + ' |\n|---|' + '---|' * 8)
for nm in names + ['universo', 'SPY']:
    L.append(f'| {nm} | ' + ' | '.join(f(AN.loc[y, nm], 0) for y in range(2019, 2027)) + ' |')
L.append('\n### Caso: CAGR netto di N titoli presi a sorte fra i promossi V3 (1000 estrazioni): 5° / 50° / 95° percentile, e posizione delle 6 versioni del punteggio')
for N in (15, 30):
    for p in PER:
        v = RND[N][p]
        sv = R[(R.gruppo == f'punteggio{N}') & (R.periodo == p)]
        pos = ', '.join(f"{nm.split('|',1)[1].strip()} {f(c)} (pct {np.mean(v < c)*100:.0f})" for nm, c in zip(sv.variante, sv.CAGR))
        L.append(f'- top {N}, {p}: caso {f(np.percentile(v, 5))} / {f(np.percentile(v, 50))} / {f(np.percentile(v, 95))}; ' + pos)
# confronto diretto fra misure di redditivita' (stesse N e pesi), t della differenza trimestrale netta
L.append('\n### Differenze fra misure di redditività (t della differenza trimestrale netta, 2012-26 / fuori campione)')
oos = [d for d in DATES if PER['Fuori campione 2020-24'][0] <= d <= PER['Fuori campione 2020-24'][1]]
for N in (15, 30):
    for eq in ('PEG 30', 'pesi uguali'):
        a = {pn: NET[f'V4 top {N} | {pn} | {eq}'] for pn in PROF}
        L.append(f'- top {N}, {eq}: ' + '; '.join(f'{x} − {y}: t {fn(tstat(a[x] - a[y]))} / {fn(tstat(a[x][oos] - a[y][oos]))}'
                                               for x, y in [('Margine EBITDA', 'ROE'), ('EBITDA/EV', 'ROE'), ('EBITDA/EV', 'Margine EBITDA')]))
# sovrapposizione fra versioni di punteggio
L.append('\n### Sovrapposizione media dei titoli scelti (top 30, PEG 30)')
k = [f'V4 top 30 | {pn} | PEG 30' for pn in PROF]
for i in range(3):
    for j in range(i + 1, 3):
        ov = np.mean([len(set(SEL[k[i]][t]) & set(SEL[k[j]][t])) / max(len(SEL[k[i]][t]), 1) for t in DATES if SEL[k[i]][t]])
        L.append(f'- {k[i].split("|")[1].strip()} vs {k[j].split("|")[1].strip()}: {ov:.0%}')
# quota di PEG 1-2 nei promossi V3 e nei top 30
b = F[V3]; L.append(f"\nQuota posizioni V3 con PEG 1-2: {(b.peg >= 1).mean():.0%}; PEG mediano V3 {b.peg.median():.2f}")
open(f'{OUT}/garp_peg_tabelle.md', 'w').write('\n'.join(L))
print('\n'.join(L))
