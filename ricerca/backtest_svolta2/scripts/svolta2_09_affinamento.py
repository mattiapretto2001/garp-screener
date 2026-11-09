# Svolta, seconda parte: (1) diagnosi del 2025-26 di B1, (2) rendimenti anno per anno, (3) varianti di affinamento.
# Usa le cache di svolta_05_features.py (cache/features.pkl, cache/rq.pkl, cache/sic.json, cache/universe.csv).
# Stesse definizioni di svolta_06_backtest.py (criteri, Moonshot, GARP, costi, periodi). Uscita: results/svolta2_*.
import pandas as pd, numpy as np, os, json
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
OUT = f'{BASE}/results'; os.makedirs(OUT, exist_ok=True)
TODAY = pd.Timestamp('2026-11-03')
F = pd.read_pickle(f'{BASE}/cache/features.pkl')
RQ = pd.read_pickle(f'{BASE}/cache/rq.pkl')
F = F[(F.mcap >= 150e6) & (F.rev_ttm > 0) & F.r3.notna()].copy().reset_index(drop=True)
F['key'] = F.ticker
DATES = sorted(F.date.unique())
PER = {'IS 2012-19': (pd.Timestamp('2012-01-01'), pd.Timestamp('2019-12-31')),
       'OOS 2020-24': (pd.Timestamp('2020-01-01'), pd.Timestamp('2024-09-30')),
       'Recente 2025-26': (pd.Timestamp('2024-12-31'), pd.Timestamp('2026-09-30'))}
COST_SIDE = 1 / 300 + 0.0035 / 2
sicj = json.load(open(f'{BASE}/cache/sic.json'))
uni = pd.read_csv(f'{BASE}/cache/universe.csv')
F['nome'] = F.cik.map(dict(zip(uni.cik, uni.name)))
F['sic_desc'] = F.cik.map(lambda c: (sicj.get(str(c)) or [None, None])[1])
sic = F.sic.fillna(0)
F['sic2'] = (sic // 100).astype(int)
industrial = sic.between(3500, 3699) | sic.between(3800, 3899)
d_opm = F.opm_ttm - F.opm_ttm4
d_gm = F.gm_ttm - F.gm_ttm4
accel = (F.yoy0 >= F[['yoy1', 'yoy2', 'yoy3']].mean(axis=1)) | (F.yoy0 >= F.yoy1 + 0.03)
netdebt = F.debt - F.liq
burn = -F.fcf_ttm
def C1f(dmin=0.05, lo=-0.15, hi=0.20, qalt=0.08, last2=True):
    m = ((d_opm >= dmin) | (F.opm_q0 - F.opm_q12 >= qalt)) & F.opm_ttm.between(lo, hi)
    if last2: m &= ~(F.opm_q0 < F.opm_q6)
    return m.fillna(False).astype(bool)
C1 = C1f()
# punteggio (identico a svolta_06)
def score():
    s = pd.Series(0.0, index=F.index)
    x = (d_opm * 100).clip(lower=0)
    tr = np.interp(x.fillna(0), [0, 5, 10, 15], [0, 10, 18, 25]) + np.where((F.opm_ttm4 < 0) & (F.opm_ttm >= 0), 5, 0)
    s += np.minimum(tr, 25)
    gm = F.gm_ttm
    s += np.select([gm >= 0.75, gm >= 0.60, gm >= 0.55, gm >= 0.40], [10, 7, 4, 2], 0) + np.where(d_gm >= 0.02, 5, 0)
    s -= np.where(industrial & (gm < 0.55), 1, 0)
    y = F.yoy0
    s += np.select([y.between(0.20, 0.30), y.between(0.30, 0.45), y.between(0.45, 0.60)], [6, 10, 8], 0) + np.where(accel, 5, 0)
    s += np.where(F.fcf_ttm > 0, 5, 0) + np.where(netdebt < 0, 3, 0) + np.where(F.dil_yoy < 0.02, 2, 0)
    rl = F.price / F.lo52
    s += np.select([rl.between(1.2, 1.8), rl.between(1.8, 2.5)], [10, 5], 0) - np.where(F.price > 0.95 * F.hi52, 3, 0)
    return (s.clip(lower=0) * 100 / 75).round(1)
F['score'] = score()
MOON = (F.mcap.between(150e6, 15e9) & (F.rev_ttm > 100e6) & (F.yoy0 > 0.25) & ((F.gm_ttm > 0.25) | F.gm_ttm.isna()) &
        (F.price >= 0.7 * F.hi52) & (F.price > F.ma200) & ((F.fcf_ttm > 0) | (F.liq / burn > 2)) &
        ((F.debt <= 2 * F.liq) | (netdebt / F.ebitda_ttm.where(F.ebitda_ttm > 0) <= 2.5)) & ~(F.dil_yoy >= 0.15)).fillna(False)
garp_sec = ~(sic.between(6000, 6799) | sic.between(4900, 4999) | sic.between(1200, 1399) | sic.between(2900, 2999) | sic.between(4610, 4619) |
             sic.between(1000, 1099) | sic.between(1400, 1499) | sic.between(2600, 2699) | sic.between(2800, 2829) | sic.between(2840, 2899) | sic.between(3300, 3399))
epsg = F.eps_ttm / F.eps_ttm4 - 1
peg = (F.mcap / F.ni_ttm) / (epsg * 100)
GARP = (garp_sec & (F.ni_ttm > 0) & (epsg > 0) & (peg > 0) & (peg < 1) & (F.equity > 0) & (F.ni_ttm / F.equity > 0.15) & (F.debt / F.equity < 1) &
        (F.fcf_ttm > 0) & (F.yoy0 > 0.05) & (F.eps_q0 / F.eps_q12.where(F.eps_q12 > 0) - 1 > 0.05) & (F.rev_cagr > 0.10)).fillna(False)
B0m = ((F.gm_ttm >= 0.55) & F.yoy0.between(0.20, 0.60) & F.mcap.between(1e9, 15e9)).fillna(False)
B1m = B0m & C1
above200 = (F.price > F.ma200).fillna(False)
SOFT = sic.between(7370, 7379)          # software e servizi informatici (SIC 737x)
APPSW = sic.isin([7372])                # software preconfezionato/applicativo (SIC 7372)
F['ps'] = F.mcap / F.rev_ttm

# ------------------------------------------------------------------ motore (come svolta_06)
univ_r = F.groupby('date').r3.mean(); spy_r = F.groupby('date').spy3.first()
def sel(mask, topn=None, cap_sector=None):
    S = {}
    d = F[mask]
    for t in DATES:
        x = d[d.date == t].sort_values(['score', 'mcap'], ascending=[False, False])
        if cap_sector: x = x.groupby('sic2', sort=False).head(cap_sector)
        if topn: x = x.head(topn)
        S[t] = list(x.key)
    return S
def union(*Ss): return {t: list(dict.fromkeys(sum((S[t] for S in Ss), []))) for t in DATES}
def run(S):
    r, n, cost, prev = {}, {}, {}, []
    for t in DATES:
        k = S[t]; n[t] = len(k)
        r[t] = RQ.loc[t].reindex(k).fillna(0.0).mean() if k else 0.0
        sold = len(set(prev) - set(k)) / len(prev) if prev else 0
        bought = len(set(k) - set(prev)) / len(k) if k else 0
        cost[t] = COST_SIDE * (sold + bought); prev = k
    return pd.Series(r), pd.Series(n), pd.Series(cost)
def years(ds): return (min(ds[-1] + pd.DateOffset(months=3), TODAY) - ds[0]).days / 365.25
def cagr(r, ds): return (1 + r).prod() ** (1 / years(ds)) - 1
def maxdd(r): w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()
def tstat(x):
    x = pd.Series(x).dropna(); return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else np.nan
RES, SER, SEL = [], {}, {}
def ev(name, S, base='B1', group=''):
    r, n, c = run(S); SER[name] = r; SER[name + ' | costi'] = r - c; SEL[name] = S
    for p, (a, b) in PER.items():
        ds = [d for d in DATES if a <= d <= b]
        rr, uu, cc = r[ds], univ_r[ds], c[ds]
        row = dict(gruppo=group, variante=name, periodo=p, n_medio=n[ds].mean(), trim_vuoti=int((n[ds] == 0).sum()),
                   CAGR=cagr(rr, ds), CAGR_costi=cagr(rr - cc, ds), CAGR_univ=cagr(uu, ds), CAGR_SPY=cagr(spy_r[ds], ds),
                   t_vs_univ=tstat(rr - uu), maxDD=maxdd(rr), costo_annuo=cc.sum() / years(ds))
        if base in SER and base != name:
            rb = SER[base][ds]; row['d_vs_base'] = row['CAGR'] - cagr(rb, ds); row['t_vs_base'] = tstat(rr - rb)
        RES.append(row)
    return S

ev('B1', sel(B1m), group='rif')
ev('B1 top 8', sel(B1m, 8), group='rif')
ev('B0', sel(B0m), group='rif')
ev('Moonshot', sel(MOON), group='rif')
ev('GARP', sel(GARP), group='rif')
# (a) momentum leggero
ev('a) B1 + prezzo sopra media 200 gg', sel(B1m & above200), group='a')
# (b) limite per settore SIC a 2 cifre (i migliori per punteggio)
ev('b) B1 max 2 per settore SIC2', sel(B1m, cap_sector=2), group='b')
ev('b) B1 max 3 per settore SIC2', sel(B1m, cap_sector=3), group='b')
# (c) combinazione con Moonshot
ev('c) B1 e Moonshot (entrambi)', sel(B1m & MOON), group='c')
ev('c) B1 oppure Moonshot (unione)', union(sel(B1m), sel(MOON)), group='c')
# (e) diagnostico: senza software
ev('e) B1 senza software applicativo (SIC 7372)', sel(B1m & ~APPSW), group='e')
ev('e) B1 senza tutto il software/IT (SIC 737x)', sel(B1m & ~SOFT), group='e')
# combinazioni a+b
ev('a+b) B1 + media 200 gg + max 3 per settore', sel(B1m & above200, cap_sector=3), group='ab')
# (d) griglia di sensibilita' sulle soglie del margine operativo
GRID = []
for dmin in (0.03, 0.04, 0.05, 0.06, 0.08):
    for lo in (-0.10, -0.15, -0.20, -0.25):
        for hi in (0.15, 0.20, 0.25, 0.30):
            nm = f'd) +{dmin*100:.0f} pt, livello {lo*100:.0f}/+{hi*100:.0f}%'
            ev(nm, sel(B0m & C1f(dmin, lo, hi)), group='d')
            GRID.append((dmin, lo, hi, nm))
ev('d) +5 pt senza alternativa trimestrale +8', sel(B0m & C1f(qalt=9.0)), group='d2')
ev('d) +5 pt, alternativa trimestrale +5', sel(B0m & C1f(qalt=0.05)), group='d2')
ev('d) +5 pt, alternativa trimestrale +12', sel(B0m & C1f(qalt=0.12)), group='d2')

R = pd.DataFrame(RES); R.to_csv(f'{OUT}/svolta2_varianti.csv', index=False)
SR = pd.DataFrame(SER).assign(universo=univ_r, SPY=spy_r); SR.to_csv(f'{OUT}/svolta2_serie.csv')

# ------------------------------------------------------------------ anno per anno
Y = SR.copy(); Y.index = Y.index + pd.offsets.QuarterEnd(1)
A = (1 + Y).groupby(Y.index.year).prod() - 1
A.to_csv(f'{OUT}/svolta2_annuali.csv')

# ------------------------------------------------------------------ diagnosi 2025-26
rec = [t for t in DATES if t >= pd.Timestamp('2024-12-31')]
rows = []
for name, mask in [('B1', B1m), ('Moonshot', MOON), ('GARP', GARP)]:
    for t in rec:
        x = F[mask & (F.date == t)]
        n = len(x)
        for r in x.itertuples():
            rows.append(dict(strategia=name, data=t.date(), ticker=r.ticker, nome=r.nome, sic=r.sic, settore=r.sic_desc, r3=r.r3,
                             contributo=r.r3 / n, mcap_mld=r.mcap / 1e9, ps=r.ps, ricavi_aa=r.yoy0, marg_lordo=r.gm_ttm,
                             marg_op=r.opm_ttm, marg_op_1a=r.opm_ttm4, prezzo_su_ma200=r.price / r.ma200, prezzo_su_max52=r.price / r.hi52,
                             score=r.score, anche_moonshot=bool(MOON[r.Index]), anche_garp=bool(GARP[r.Index])))
D = pd.DataFrame(rows); D.to_csv(f'{OUT}/svolta2_promossi_recenti.csv', index=False)
txt = []
U = F[F.date.isin(rec)]
def grp(s):
    s = s.fillna(0)
    return np.select([s.between(7370, 7379), s == 3674, s.between(3570, 3579) | s.between(3660, 3699) | s.between(3600, 3673) | s.between(3675, 3679),
                      s.between(2830, 2836) | s.between(8730, 8739), s.between(3800, 3899) | s.between(8000, 8099), s.between(6000, 6799), s.between(4800, 4899)],
                     ['Software e IT (737x)', 'Semiconduttori (3674)', 'Elettronica/hardware', 'Farmaci e biotech', 'Strumenti/salute', 'Finanza', 'Telecom/media'], 'Altro')
F['gruppo'] = grp(F.sic)
D['gruppo'] = grp(D.sic)
txt.append('Composizione per gruppo di settore (quota di posizioni-trimestre, 12/2024-09/2026):')
for name in ['B1', 'Moonshot', 'GARP']:
    x = D[D.strategia == name]
    txt.append(f'  {name}: ' + ', '.join(f'{k} {v:.0%}' for k, v in x.gruppo.value_counts(normalize=True).items()) + f' (posizioni {len(x)})')
txt.append('\nRendimento medio a 3 mesi per gruppo nell\'universo (equipesato), per data di ribilanciamento:')
G = F[F.date.isin(rec)].groupby(['date', 'gruppo']).r3.mean().unstack()
txt.append(G.round(3).to_string())
txt.append('\nRendimento medio per gruppo fra le società 1-15 Mld$ con margine lordo >=55% e ricavi +20/60% (B0), per data:')
txt.append(F[B0m & F.date.isin(rec)].groupby(['date', 'gruppo']).r3.mean().unstack().round(3).to_string())
txt.append('\nValutazioni di partenza (mediana prezzo/ricavi TTM) per data: B1 / Moonshot / GARP / B0 / universo')
for t in DATES:
    if t < pd.Timestamp('2016-12-31'): continue
    v = [F[m & (F.date == t)].ps.median() for m in (B1m, MOON, GARP, B0m, pd.Series(True, index=F.index))]
    txt.append(f'  {t.date()}: ' + ' / '.join(f'{x:.1f}' for x in v))
txt.append('\nMediana prezzo/ricavi B1 per periodo: ' + ', '.join(
    f'{p} {F[B1m & F.date.between(a, b)].ps.median():.1f} (universo {F[F.date.between(a, b)].ps.median():.1f}, B0 {F[B0m & F.date.between(a, b)].ps.median():.1f})' for p, (a, b) in PER.items()))
txt.append('Quota software/IT (737x) in B1 per periodo: ' + ', '.join(f'{p} {SOFT[B1m & F.date.between(a, b)].mean():.0%}' for p, (a, b) in PER.items()))
txt.append('Quota software/IT (737x) in Moonshot per periodo: ' + ', '.join(f'{p} {SOFT[MOON & F.date.between(a, b)].mean():.0%}' for p, (a, b) in PER.items()))
txt.append('Quota sopra media 200 gg in B1 per periodo: ' + ', '.join(f'{p} {above200[B1m & F.date.between(a, b)].mean():.0%}' for p, (a, b) in PER.items()))
txt.append('Sovrapposizione B1 con Moonshot (quota posizioni B1 anche Moonshot): ' + ', '.join(f'{p} {MOON[B1m & F.date.between(a, b)].mean():.0%}' for p, (a, b) in PER.items()))
# software nell'universo: rendimento a 3 mesi del gruppo software vs resto, per anno solare del rendimento
F['anno_r'] = (F.date + pd.offsets.QuarterEnd(1)).dt.year
Z = F.groupby(['anno_r', SOFT.rename('sw')]).r3.mean().unstack()
txt.append('\nRendimento trimestrale medio dell\'universo: software/IT (True) contro il resto (False), per anno:\n' + Z.round(3).to_string())
# B1 2026 senza il titolo peggiore di ogni trimestre / senza i due peggiori titoli dell'anno
r26 = [t for t in DATES if (t + pd.offsets.QuarterEnd(1)).year == 2026]
b1 = SEL['B1']
def chain(f): return np.prod([1 + f(t) for t in r26]) - 1
drop_worst = chain(lambda t: RQ.loc[t].reindex(b1[t]).fillna(0).sort_values().iloc[1:].mean() if len(b1[t]) > 1 else 0)
txt.append(f'\nB1 2026: {chain(lambda t: RQ.loc[t].reindex(b1[t]).fillna(0).mean()):.1%}; senza il peggiore di ogni trimestre: {drop_worst:.1%}')
x26 = D[(D.strategia == 'B1') & D.data.isin([t.date() for t in r26])]
w = x26.groupby('ticker').contributo.sum().sort_values()
txt.append('Contributo cumulato (somma dei contributi trimestrali, punti %) dei titoli B1 nel 2026, peggiori e migliori:\n' + (w * 100).round(1).to_string())
for k in (1, 2, 3):
    bad = set(w.index[:k])
    v = chain(lambda t: RQ.loc[t].reindex([z for z in b1[t] if z not in bad]).fillna(0).mean() if [z for z in b1[t] if z not in bad] else 0)
    txt.append(f'B1 2026 senza i {k} titoli che hanno pesato di piu\' ({", ".join(sorted(bad))}): {v:.1%}')
open(f'{OUT}/svolta2_diagnosi.txt', 'w').write('\n'.join(txt))
print('\n'.join(txt))
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
print(R[R.gruppo != 'd'][['variante', 'periodo', 'n_medio', 'trim_vuoti', 'CAGR', 'CAGR_costi', 'CAGR_univ', 't_vs_univ', 'd_vs_base', 't_vs_base', 'maxDD']].round(3).to_string())
print(A[['B1', 'B1 top 8', 'B0', 'Moonshot', 'GARP', 'universo', 'SPY']].round(3).to_string())
