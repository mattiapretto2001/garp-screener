# Backtest dei criteri "Svolta": filtri, punteggio, portafogli concentrati, esperimenti -> results/
import pandas as pd, numpy as np, os, sys
BASE = os.path.dirname(os.path.abspath(__file__)) + '/..'
OUT = f'{BASE}/results'; os.makedirs(OUT, exist_ok=True)
TODAY = pd.Timestamp('2026-11-03')
F = pd.read_pickle(f'{BASE}/cache/features.pkl')
RQ = pd.read_pickle(f'{BASE}/cache/rq.pkl')          # date x ticker, rendimento dei 3 mesi successivi
F = F[(F.mcap >= 150e6) & (F.rev_ttm > 0) & F.r3.notna()].copy()   # universo
F['key'] = F.ticker
DATES = sorted(F.date.unique())
PER = {'IS 2012-19': (pd.Timestamp('2012-01-01'), pd.Timestamp('2019-12-31')),
       'OOS 2020-24': (pd.Timestamp('2020-01-01'), pd.Timestamp('2024-09-30')),
       'Recente 2025-26': (pd.Timestamp('2024-12-31'), pd.Timestamp('2026-09-30'))}
def per_of(d):
    for k, (a, b) in PER.items():
        if a <= d <= b: return k
COST_SIDE = 1 / 300 + 0.0035 / 2   # 1 EUR su ~300 EUR + meta' spread 0,35% (centro di 0,2-0,5%)

# ---------------------------------------------------------------- criteri Svolta
g = lambda c: F[c]
sic = F.sic.fillna(0)
industrial = sic.between(3500, 3699) | sic.between(3800, 3899)
low_gm_sector = sic.between(1500, 1799) | sic.between(3710, 3716) | sic.between(1000, 1499) | sic.between(2600, 2699) | sic.between(2800, 2829) | sic.between(3300, 3399)
d_opm = F.opm_ttm - F.opm_ttm4
d_gm = F.gm_ttm - F.gm_ttm4
accel = (F.yoy0 >= F[['yoy1', 'yoy2', 'yoy3']].mean(axis=1)) | (F.yoy0 >= F.yoy1 + 0.03)
netdebt = F.debt - F.liq
burn = -F.fcf_ttm
CRIT = {
 'C1 margine operativo +5 pt (livello -15/+20%)':
    (((d_opm >= 0.05) | (F.opm_q0 - F.opm_q12 >= 0.08)) & F.opm_ttm.between(-0.15, 0.20) & ~(F.opm_q0 < F.opm_q6)),
 'C2 margine lordo >=55% e non in calo':
    (((F.gm_ttm >= 0.55) | (industrial & (F.gm_ttm >= 0.40))) & (d_gm >= 0)),
 'C3 ricavi +20/60% e in accelerazione':
    (F.yoy0.between(0.20, 0.60) & accel & ~(F.acq_ttm.fillna(0) > 0.2 * F.rev_ttm4)),
 'C5 primo utile / risultato operativo appena positivo':
    (((F.opinc_ttm > 0) & (F.opinc_ttm4 <= 0)) | ((F.ni_ttm > 0) & (F.ni_ttm4 <= 0)) |
     ((F.opinc_q0 > 0) & (F[['opinc_q3', 'opinc_q6', 'opinc_q9', 'opinc_q12']].min(axis=1) <= 0)) | F.opm_ttm.between(0, 0.05)),
 'C6 capitalizzazione 1-15 Mld$': F.mcap.between(1e9, 15e9),
 'C7 prezzo <=2,5x minimo 52 sett. e 60-97% del massimo':
    ((F.price <= 2.5 * F.lo52) & (F.price >= 0.60 * F.hi52) & (F.price <= 0.97 * F.hi52)),
 'C8 cassa solida (runway >=2 anni, diluizione <10%, debito)':
    (((F.fcf_ttm > 0) | (F.liq / burn >= 2)) & ~(F.dil_yoy >= 0.10) &
     (((F.ebitda_ttm > 0) & (netdebt / F.ebitda_ttm < 2.5)) | (netdebt <= 0))),
 'X esclusione settori a margine basso': ~low_gm_sector,
}
CRIT = {k: v.fillna(False).astype(bool) for k, v in CRIT.items()}
ALL = np.logical_and.reduce(list(CRIT.values()))

# punteggio (solo le voci ricostruibili: 75 punti su 100, riportati a 0-100)
def score(F):
    s = pd.Series(0.0, index=F.index)
    x = (d_opm * 100).clip(lower=0)
    tr = np.interp(x.fillna(0), [0, 5, 10, 15], [0, 10, 18, 25])
    tr = tr + np.where((F.opm_ttm4 < 0) & (F.opm_ttm >= 0), 5, 0)
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
F['score'] = score(F)

# ---------------------------------------------------------------- Moonshot e GARP base (stessi proxy del rapporto 27/10)
MOON = (F.mcap.between(150e6, 15e9) & (F.rev_ttm > 100e6) & (F.yoy0 > 0.25) & ((F.gm_ttm > 0.25) | F.gm_ttm.isna()) &
        (F.price >= 0.7 * F.hi52) & (F.price > F.ma200) & ((F.fcf_ttm > 0) | (F.liq / burn > 2)) &
        ((F.debt <= 2 * F.liq) | (netdebt / F.ebitda_ttm.where(F.ebitda_ttm > 0) <= 2.5)) & ~(F.dil_yoy >= 0.15)).fillna(False)
garp_sec = ~(sic.between(6000, 6799) | sic.between(4900, 4999) | sic.between(1200, 1399) | sic.between(2900, 2999) | sic.between(4610, 4619) |
             sic.between(1000, 1099) | sic.between(1400, 1499) | sic.between(2600, 2699) | sic.between(2800, 2829) | sic.between(2840, 2899) | sic.between(3300, 3399))
epsg = F.eps_ttm / F.eps_ttm4 - 1
peg = (F.mcap / F.ni_ttm) / (epsg * 100)
GARP = (garp_sec & (F.ni_ttm > 0) & (epsg > 0) & (peg > 0) & (peg < 1) & (F.equity > 0) & (F.ni_ttm / F.equity > 0.15) & (F.debt / F.equity < 1) &
        (F.fcf_ttm > 0) & (F.yoy0 > 0.05) & (F.eps_q0 / F.eps_q12.where(F.eps_q12 > 0) - 1 > 0.05) & (F.rev_cagr > 0.10)).fillna(False)

# ---------------------------------------------------------------- motori
univ_r = F.groupby('date').r3.mean()
spy_r = F.groupby('date').spy3.first()
def sel_lists(mask, topn=None, minscore=None):
    S = {}
    d = F[mask]
    for t in DATES:
        x = d[d.date == t]
        if minscore is not None: x = x[x.score >= minscore]
        if topn: x = x.sort_values(['score', 'mcap'], ascending=[False, False]).head(topn)
        S[t] = list(x.key)
    return S
def rq(t, keys):
    v = RQ.loc[t].reindex(keys).fillna(0.0) if keys else pd.Series(dtype=float)
    return v
def run_rebal(S):
    r, n, cost, prev = {}, {}, {}, []
    for t in DATES:
        k = S[t]; n[t] = len(k)
        r[t] = rq(t, k).mean() if k else 0.0
        sold = len(set(prev) - set(k)) / len(prev) if prev else 0
        bought = len(set(k) - set(prev)) / len(k) if k else 0
        cost[t] = COST_SIDE * (sold + bought); prev = k
    return pd.Series(r), pd.Series(n), pd.Series(cost)
def run_hold(S, H):
    """detenzione H mesi a tranche: ogni trimestre si compra una coorte e la si tiene H mesi (buy and hold)"""
    k = H // 3; coh = {}
    for i, t in enumerate(DATES):
        keys = S[t]
        if not keys: coh[t] = pd.Series(0.0, index=DATES[i:i + k]); continue
        G = pd.DataFrame({DATES[i + j]: rq(DATES[i + j], keys) for j in range(k) if i + j < len(DATES)})
        cum = (1 + G).cumprod(axis=1)
        val = cum.mean(axis=0); prevv = val.shift(1).fillna(1.0)
        coh[t] = val / prevv - 1
    r, n, cost = {}, {}, {}
    for i, t in enumerate(DATES):
        act = [coh[DATES[j]][t] for j in range(max(0, i - k + 1), i + 1) if t in coh[DATES[j]].index]
        r[t] = np.mean(act); n[t] = sum(len(S[DATES[j]]) for j in range(max(0, i - k + 1), i + 1))
        cost[t] = COST_SIDE * 2 / k
    return pd.Series(r), pd.Series(n), pd.Series(cost)
Fi = F.set_index(['date', 'key'])
def intact(t, key):
    try: x = Fi.loc[(t, key)]
    except KeyError: return False
    opm_down2 = (x.opm_ttm < x.opm_ttm1) and (x.opm_ttm1 < x.opm_ttm2)
    return (not opm_down2) and (x.rev_ttm >= x.rev_ttm1)
def run_winner(mask, topn=None, minscore=None):
    """non vendere il vincitore se la tesi e' intatta: si tiene finche' margine operativo (2 trimestri di calo) e ricavi non peggiorano"""
    S = sel_lists(mask, None, minscore)
    sc = F.set_index(['date', 'key']).score
    r, n, cost, held = {}, {}, {}, []
    H = {}
    for t in DATES:
        keep = [k for k in held if intact(t, k)]
        new = [k for k in sorted(S[t], key=lambda k: -sc.get((t, k), 0)) if k not in keep]
        cur = keep + (new[:max(0, topn - len(keep))] if topn else new)
        r[t] = rq(t, cur).mean() if cur else 0.0; n[t] = len(cur)
        sold = len(set(held) - set(cur)) / len(held) if held else 0
        bought = len(set(cur) - set(held)) / len(cur) if cur else 0
        cost[t] = COST_SIDE * (sold + bought); held = cur; H[t] = cur
    return pd.Series(r), pd.Series(n), pd.Series(cost), H
def maxdd(r):
    w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()
def years(ds):
    a = ds[0]; b = min(ds[-1] + pd.DateOffset(months=3), TODAY); return (b - a).days / 365.25
def cagr(r, ds): return (1 + r).prod() ** (1 / years(ds)) - 1
def tstat(x):
    x = pd.Series(x).dropna(); return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else np.nan
def hits(S, ds):
    ds = [d for d in ds if d + pd.DateOffset(months=24) <= TODAY]
    if not ds: return np.nan, np.nan, np.nan
    U = F[F.date.isin(ds)]
    u2 = (U.max24 >= 2)
    sel = set((t, k) for t in ds for k in S[t])
    m = U.set_index(['date', 'key']).index.isin(list(sel))
    p = u2[m].mean() if m.sum() else np.nan
    return p, u2.mean(), (u2 & m).sum() / max(u2.sum(), 1)
def cohort_extra(S, ds, H):
    ex = []
    for t in ds:
        if not S[t]: continue
        U = F[F.date == t]
        if H > 3 and t + pd.DateOffset(months=H) > TODAY + pd.Timedelta(days=5): continue
        ex.append(U[U.key.isin(S[t])][f'r{H}'].mean() - U[f'r{H}'].mean())
    return np.mean(ex) if ex else np.nan
RES = []; SERIES = {}
def evaluate(name, S=None, mode='rebal', H=3, mask=None, topn=None, minscore=None, base=None, group=''):
    if mode == 'rebal': r, n, c = run_rebal(S)
    elif mode == 'hold': r, n, c = run_hold(S, H)
    else: r, n, c, S = run_winner(mask, topn, minscore)
    SERIES[name] = r; SERIES[name + ' | costi'] = r - c
    for p, (a, b) in PER.items():
        ds = [d for d in DATES if a <= d <= b]
        rr, uu, ss, cc = r[ds], univ_r[ds], spy_r[ds], c[ds]
        h = hits(S, ds)
        row = dict(gruppo=group, esperimento=name, periodo=p, n_medio=n[ds].mean(), trim_vuoti=int((n[ds] == 0).sum()),
                   CAGR=cagr(rr, ds), CAGR_costi=cagr(rr - cc, ds), CAGR_univ=cagr(uu, ds), CAGR_SPY=cagr(ss, ds),
                   maxDD=maxdd(rr), maxDD_univ=maxdd(uu), t_vs_univ=tstat(rr - uu), t_vs_SPY=tstat(rr - ss),
                   trim_battuto_univ=(rr > uu).mean(), costo_annuo=cc.sum() / years(ds),
                   hit2x_24m=h[0], hit2x_24m_univ=h[1], raddoppi_intercettati=h[2])
        for HH in (3, 6, 12, 24): row[f'extra_coorte_{HH}m'] = cohort_extra(S, ds, HH)
        if base is not None:
            rb = SERIES[base][ds]; row['t_vs_base'] = tstat(rr - rb); row['d_CAGR'] = row['CAGR'] - cagr(rb, ds)
        row['extra_vs_univ'] = row['CAGR'] - row['CAGR_univ']; row['extra_vs_SPY'] = row['CAGR'] - row['CAGR_SPY']
        RES.append(row)
    return S

# ---------------------------------------------------------------- esperimenti
NCRIT = pd.DataFrame(CRIT).sum(axis=1)
B0m = ((F.gm_ttm >= 0.55) & F.yoy0.between(0.20, 0.60) & F.mcap.between(1e9, 15e9)).fillna(False)   # "filtro base" della prova rapida
S6m = (NCRIT >= 6); S7m = (NCRIT >= 7)
BS = 'S0 Svolta completa (tutti gli 8 criteri)'
S0 = evaluate(BS, sel_lists(ALL), group='base')
evaluate('S7 Svolta: almeno 7 criteri su 8', sel_lists(S7m), group='base')
evaluate('S6 Svolta: almeno 6 criteri su 8', sel_lists(S6m), group='base')
evaluate('B0 filtro base (marg. lordo >=55%, ricavi +20/60%, 1-15 Mld$)', sel_lists(B0m), group='base')
evaluate('M0 Moonshot base (ricalcolato)', sel_lists(MOON), group='confronto')
evaluate('G0 GARP base (ricalcolato)', sel_lists(GARP), group='confronto')
for N in (3, 4, 8):
    evaluate(f'S0 completa: top {N}', sel_lists(ALL, N), base=BS, group='concentrati')
for N in (3, 4, 8):
    evaluate(f'S6 (>=6 su 8): top {N} per punteggio', sel_lists(S6m, N), base='S6 Svolta: almeno 6 criteri su 8', group='concentrati')
    evaluate(f'S6 (>=6 su 8): top {N}, solo se punteggio >=65', sel_lists(S6m, N, 65), base='S6 Svolta: almeno 6 criteri su 8', group='concentrati')
for N in (3, 4, 8):
    evaluate(f'B0 filtro base: top {N} per punteggio', sel_lists(B0m, N), base='B0 filtro base (marg. lordo >=55%, ricavi +20/60%, 1-15 Mld$)', group='concentrati')
LARGE = CRIT['C6 capitalizzazione 1-15 Mld$'] & CRIT['X esclusione settori a margine basso']
for N in (3, 4, 8):
    evaluate(f'Punteggio puro: top {N} fra tutte le 1-15 Mld$', sel_lists(LARGE, N), group='concentrati')
# togli un criterio alla volta (dalla versione completa)
for k in CRIT:
    m = np.logical_and.reduce([v for kk, v in CRIT.items() if kk != k])
    evaluate(f'S0 senza {k}', sel_lists(m), base=BS, group='ablazione')
# aggiungi un criterio alla volta al filtro base (contributo di ciascuno, con piu' titoli)
B0n = 'B0 filtro base (marg. lordo >=55%, ricavi +20/60%, 1-15 Mld$)'
for k in CRIT:
    if k.startswith('C6'): continue
    evaluate(f'B0 + {k}', sel_lists(B0m & CRIT[k]), base=B0n, group='contributo')
evaluate('B0 + solo accelerazione dei ricavi', sel_lists(B0m & accel.fillna(False)), base=B0n, group='contributo')
evaluate('B0 + margine operativo in salita (>=+5 pt, senza limiti di livello)', sel_lists(B0m & (d_opm >= 0.05).fillna(False)), base=B0n, group='contributo')
# solo qualita'
Q1 = CRIT['C2 margine lordo >=55% e non in calo'] & ((d_opm >= 0.05).fillna(False))
QN = "Q solo qualita': margine lordo >=55% non in calo + margine op. +5 pt"
evaluate(QN, sel_lists(Q1), base=B0n, group='qualita')
Q2 = Q1 & CRIT['C6 capitalizzazione 1-15 Mld$']
evaluate("Q solo qualita' + capitalizzazione 1-15 Mld$", sel_lists(Q2), base=B0n, group='qualita')
for N in (3, 4, 8):
    evaluate(f"Q solo qualita': top {N} per punteggio", sel_lists(Q1, N), base=QN, group='qualita')
# sensibilita': margine lordo mancante = promosso (come Yahoo)
C2b = ((F.gm_ttm >= 0.55) | (industrial & (F.gm_ttm >= 0.40)) | F.gm_ttm.isna()) & ((d_gm >= 0) | d_gm.isna())
CR2 = dict(CRIT); CR2['C2 margine lordo >=55% e non in calo'] = C2b.fillna(False)
evaluate('S6 sensibilita: margine lordo mancante = promosso', sel_lists(pd.DataFrame(CR2).sum(axis=1) >= 6), base='S6 Svolta: almeno 6 criteri su 8', group='sensibilita')
# orizzonti di detenzione
for H in (6, 12, 24):
    evaluate(f'B0 tenuti {H} mesi (tranche trimestrali)', sel_lists(B0m), mode='hold', H=H, base=B0n, group='orizzonte')
    evaluate(f'B0 top 4 tenuti {H} mesi', sel_lists(B0m, 4), mode='hold', H=H, base='B0 filtro base: top 4 per punteggio', group='orizzonte')
    evaluate(f'S6 top 4 tenuti {H} mesi', sel_lists(S6m, 4), mode='hold', H=H, base='S6 (>=6 su 8): top 4 per punteggio', group='orizzonte')
    evaluate(f'Q solo qualita\' tenuti {H} mesi', sel_lists(Q1), mode='hold', H=H, base=QN, group='orizzonte')
# regola dei vincitori
evaluate('B0 + non vendere il vincitore', mode='winner', mask=B0m, base=B0n, group='vincitori')
for N in (3, 4, 8):
    evaluate(f'B0 top {N} + non vendere il vincitore', mode='winner', mask=B0m, topn=N, base=f'B0 filtro base: top {N} per punteggio', group='vincitori')
    evaluate(f'S6 top {N} + non vendere il vincitore', mode='winner', mask=S6m, topn=N, base=f'S6 (>=6 su 8): top {N} per punteggio', group='vincitori')
evaluate('S0 completa + non vendere il vincitore', mode='winner', mask=ALL, base=BS, group='vincitori')
evaluate("Q solo qualita' + non vendere il vincitore", mode='winner', mask=Q1, base=QN, group='vincitori')
evaluate('Moonshot + non vendere il vincitore', mode='winner', mask=MOON, base='M0 Moonshot base (ricalcolato)', group='vincitori')

# approfondimento sul criterio piu' forte (C1), da leggere con cautela: test aggiunti DOPO aver visto i risultati
C1 = CRIT['C1 margine operativo +5 pt (livello -15/+20%)']
B1n = 'B1 = B0 + C1 margine operativo in svolta'
evaluate(B1n, sel_lists(B0m & C1), base=B0n, group='approfondimento')
evaluate('B0 + margine op. +5 pt e livello -15/+20% (senza controllo ultimi 2 trim.)', sel_lists(B0m & (d_opm >= 0.05).fillna(False) & F.opm_ttm.between(-0.15, 0.20)), base=B0n, group='approfondimento')
evaluate('B0 + margine op. +5 pt e ultimo trim. non peggiore di 2 trim. prima (senza limiti di livello)', sel_lists(B0m & (d_opm >= 0.05).fillna(False) & ~(F.opm_q0 < F.opm_q6).fillna(True)), base=B0n, group='approfondimento')
evaluate('B1 + C3 accelerazione ricavi', sel_lists(B0m & C1 & CRIT['C3 ricavi +20/60% e in accelerazione']), base=B1n, group='approfondimento')
evaluate('B1 + C2 margine lordo non in calo', sel_lists(B0m & C1 & CRIT['C2 margine lordo >=55% e non in calo']), base=B1n, group='approfondimento')
evaluate('B1 + C7 prezzo', sel_lists(B0m & C1 & CRIT['C7 prezzo <=2,5x minimo 52 sett. e 60-97% del massimo']), base=B1n, group='approfondimento')
for N in (3, 4, 8):
    evaluate(f'B1 top {N} per punteggio', sel_lists(B0m & C1, N), base=B1n, group='approfondimento')
evaluate('B1 + non vendere il vincitore', mode='winner', mask=B0m & C1, base=B1n, group='approfondimento')
evaluate('B1 top 4 + non vendere il vincitore', mode='winner', mask=B0m & C1, topn=4, base='B1 top 4 per punteggio', group='approfondimento')
for H in (6, 12):
    evaluate(f'B1 tenuti {H} mesi', sel_lists(B0m & C1), mode='hold', H=H, base=B1n, group='approfondimento')

R = pd.DataFrame(RES)
R.to_csv(f'{OUT}/svolta_risultati.csv', index=False)
pd.DataFrame(SERIES).assign(universo=univ_r, SPY=spy_r).to_csv(f'{OUT}/svolta_serie_trimestrali.csv')
# promossi per data (base) con punteggio
P = F[(S6m | (B0m & C1)).values].assign(n_criteri=NCRIT[(S6m | (B0m & C1))], B1=(B0m & C1)[(S6m | (B0m & C1))])[['date', 'ticker', 'cik', 'score', 'n_criteri', 'mcap', 'yoy0', 'gm_ttm', 'opm_ttm', 'opm_ttm4', 'r3', 'r12', 'r24', 'B1']]
P.to_csv(f'{OUT}/svolta_promossi.csv', index=False)
# conteggio: quanti titoli passano ciascun criterio
cnt = pd.DataFrame({k: v.groupby(F.date).mean() for k, v in CRIT.items()}).mean()
cnt.to_csv(f'{OUT}/svolta_quota_criteri.csv')
pd.set_option('display.width', 250)
print(R[['esperimento', 'periodo', 'n_medio', 'CAGR', 'CAGR_costi', 'CAGR_univ', 'CAGR_SPY', 't_vs_univ', 't_vs_base', 'maxDD', 'hit2x_24m']].round(3).to_string())
