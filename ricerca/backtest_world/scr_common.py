# scr_common (07/11): pannello panel2 + campi di scr_01, regole degli screener FISSATE PRIMA di guardare i risultati,
# motore di portafoglio e test (come tune_10: trimestrale, pesi uguali, 0,5% per operazione, euro).
#
# REGOLE (scritte prima dei test, non ritoccate dopo):
#  Moonshot "come da docstring" (M): universo GARP (settori esclusi), cap. 0,3-15 Mld$ (sotto 300 M il pannello non ha
#    dati), ricavi 12 mesi > 100 M$, ricavi del trimestre +25% sull'anno prima, margine lordo > 25%, prezzo >= 70% del
#    massimo a 52 sett. e sopra la media a 200 gg; se FCF < 0 cassa > 2 anni di consumo; debito <= 2x cassa (oppure
#    debito netto / utile operativo <= 2,5, al posto dell'EBITDA che il pannello non ha); liquidita' corrente > 1,2 se nota
#    (oppure cassa >= debito); azioni +15% al massimo in un anno. Variante "codice attuale" (M_live): senza il 70% del massimo.
#  "Crescita" (CR): le stesse regole del Moonshot (M) senza tetto di capitalizzazione, divise in piccole 0,3-2 / medie 2-15 /
#    grandi > 15 Mld$.
#  Svolta B1 (SV): come svolta_screener.py (vedi docstring), cap. 1-15 Mld$.
#  Qualita' durevole: base comune = universo GARP, cap. >= 5 Mld$, ricavi 5 anni CAGR >= 8% con al massimo 1 anno in calo
#    su 5, debito basso (cassa netta oppure debito netto / utile operativo <= 2,5), PEG <= 3 o PEG non calcolabile.
#    Q1 "rendimento del capitale": ROE >= 15% in almeno 4 degli ultimi 5 anni fiscali + margine operativo dell'ultimo anno
#       non sotto la media dei 5 anni di oltre 2 punti.
#    Q2 "margini": margine operativo >= 20% in almeno 4 dei 5 anni + stessa stabilita' + margine lordo non sceso di oltre
#       2 punti in 4 anni (se noto).
#    Q3 = Q1 oppure Q2 (la lista candidata). Universo: tutti i settori tranne banche, assicurazioni, immobiliare (vedi QU).
#  Settori esclusi, metriche adatte (S_*):
#    utilities: dividendo 12 mesi >= 3%, debito/patrimonio <= 2, ROE >= 8%, dividendo < utile (payout < 100%);
#    energia e materie prime: P/E sugli utili medi di 5 anni <= 12 (media > 0), debito/patrimonio <= 0,5;
#    finanza: ROE 12 mesi >= 12%, ROE medio 5 anni >= 10%, prezzo/patrimonio <= 2;
#    immobiliare: prezzo/patrimonio <= 1, dividendo >= 4%, debito/patrimonio <= 1,5.
import pandas as pd, numpy as np
from tune_common import run, cagr, tstat, mask, BASE_P, score, PERIODS, BASE
F = pd.read_pickle(f'{BASE}/res/panel2.pkl').reset_index(drop=True)
X = pd.read_pickle(f'{BASE}/res/scr_extra.pkl')
F = F.merge(X, on=['t', 'date'], how='left')
F['divy'] = F.divy.where(F.divy < 0.25)   # oltre 25% = errore di dati
# margine lordo per le societa' scaricate oggi
gmn = (F.gp_ttm_n / F.rev_ttm).where(lambda s: s.between(-1, 0.999))
gm4n = (F.gp_ttm4_n / F.rev_ttm4b_n).where(lambda s: s.between(-1, 0.999))
F['gm'] = F.gm.where(F.gm.notna(), gmn); F['gm4'] = F.gm4.where(F.gm4.notna(), gm4n); F['d_gm'] = F.gm - F.gm4
REB = sorted(F.date.unique())
PALL = {**PERIODS, '2012-26': ('2011-12-31', '2026-09-30')}
UNI = ~F.excl_sector
ALL = pd.Series(True, index=F.index)
mc = F.mcap_usd
# ------------------------------------------------------------ GARP
A = mask(F, BASE_P)
CORE0 = mask(F, dict(BASE_P, revq=0.20)) & (F.hi52 >= 0.8).fillna(False)
PEGG = ~(F.peg < 0.05).fillna(False)
CORE = CORE0 & (mc >= 2e9) & PEGG                       # core come proposto il 07/11 (>= 2 Mld$, guardia PEG)
RADA = UNI & ~A & (F.revq > 0.40).fillna(False) & (F.rev_cagr > 0.15).fillna(False) & (F.dshares < 0.10).fillna(True) & (mc >= 2e9)
_sc = score(F, A & PEGG)
TOP30 = pd.Series(False, index=F.index)
TOP30[F[A & PEGG].assign(s=_sc).sort_values(['date', 's'], ascending=[True, False]).groupby('date').head(30).index] = True
# ------------------------------------------------------------ Moonshot
fcf, cash, debt = F.fcf_ttm, F.cash, F.debt
runway = (fcf >= 0) | fcf.isna() | ((cash / fcf.abs()) > 2)
debt_ok = (debt <= 0) | debt.isna() | ((cash > 0) & (debt / cash <= 2)) | ((F.opi_ttm > 0) & ((debt - cash.fillna(0)) / F.opi_ttm <= 2.5))
liq_ok = F.cur_ratio.isna() | (F.cur_ratio > 1.2) | (cash >= debt)
dil_ok = F.dshares.isna() | (F.dshares < 0.15)
MB = (UNI & (F.rev_usd > 100e6) & (F.revq > 0.25) & (F.gm > 0.25) & (F.ma200 > 1) & runway & debt_ok & liq_ok & dil_ok).fillna(False)
M_LIVE = MB & mc.between(3e8, 15e9)
M = M_LIVE & (F.hi52 >= 0.70).fillna(False)
CR = MB & (F.hi52 >= 0.70).fillna(False)
SIZE3 = pd.Series(np.select([mc < 2e9, mc <= 15e9], ['piccole 0,3-2', 'medie 2-15'], 'grandi >15'), index=F.index)
# ------------------------------------------------------------ Svolta B1
LOWM = ("Engineering & Construction", "Infrastructure Operations", "Residential Construction", "Auto Manufacturers", "Auto Parts",
        "Steel", "Aluminum", "Copper", "Other Industrial Metals & Mining", "Agricultural Inputs", "Chemicals",
        "Lumber & Wood Production", "Marine Shipping")
HWW = ("Semiconductor", "Electronic", "Computer Hardware", "Communication Equipment", "Scientific & Technical", "Electrical Equipment", "Auto", "Solar")
ind = F.industry.fillna('')
hw = (F.sector == 'Industrials') | ind.apply(lambda s: any(w in s for w in HWW))
gm_ok = (F.gm >= np.where(hw, 0.40, 0.55)) & (F.d_gm.isna() | (F.d_gm >= 0))
clipd = lambda s: s.where(s.abs() <= 0.5)
d_y = clipd(F.d_opm); d_q = clipd(F.om_q - F.om_q_1y)
jump = (d_y >= 0.05) | (d_q >= 0.08)
level = F.opm.between(-0.15, 0.20)
worse = (F.om_q < F.om_q_2ago).fillna(False)
SV = (UNI & mc.between(1e9, 15e9) & ~ind.isin(LOWM) & gm_ok & F.revq.between(0.20, 0.60) & jump & level & ~worse).fillna(False)
# ------------------------------------------------------------ Qualita' durevole
yrs = range(5)
roe = pd.DataFrame({k: (F[f'ni_y{k}'] / F[f'eq_y{k}']).where(F[f'eq_y{k}'] > 0) for k in yrs})
opm = pd.DataFrame({k: (F[f'op_y{k}'] / F[f'rev_y{k}']).where(F[f'rev_y{k}'] > 0) for k in yrs})
gmy = pd.DataFrame({k: (F[f'gp_y{k}'] / F[f'rev_y{k}']).where(F[f'rev_y{k}'] > 0).where(lambda s: s.between(-1, 0.999)) for k in yrs})
gro = pd.DataFrame({k: F[f'rev_y{k}'] / F[f'rev_y{k + 1}'] - 1 for k in yrs})
full5 = roe.notna().all(axis=1) & opm.notna().all(axis=1) & gro.notna().all(axis=1)
F['roe5_n15'] = (roe >= 0.15).sum(axis=1); F['opm5_n20'] = (opm >= 0.20).sum(axis=1)
F['rev_cagr5'] = (F.rev_y0 / F.rev_y5) ** (1 / 5) - 1
F['n_down5'] = (gro < 0).sum(axis=1)
stab = opm[0] >= opm.mean(axis=1) - 0.02
gm_st = gmy[0].isna() | gmy[4].isna() | (gmy[0] >= gmy[4] - 0.02)
nd = debt.fillna(0) - cash.fillna(0)
lowdebt = (nd <= 0) | ((F.opi_ttm > 0) & (nd / F.opi_ttm <= 2.5))
pegok = ~(F.peg > 3).fillna(False)
# Nota (07/11, prima dei test): Mastercard e S&P Global nei dati sono "Financial Services", quindi il filtro di settore
# del GARP li escluderebbe. Per la qualita' l'universo principale (QU) tiene tutti i settori tranne banche, assicurazioni
# e immobiliare (dove ricavi, margini e debito non hanno lo stesso significato). Q*_G = stesse regole con le esclusioni GARP.
QU = ~ind.str.contains('Bank|Insurance|REIT|Real Estate|Mortgage', regex=True) & ~F.sector.isin(['Real Estate', 'Equity Real Estate Investment Trusts (REITs)'])
QB0 = ((mc >= 5e9) & full5 & (F.rev_cagr5 >= 0.08) & (F.n_down5 <= 1) & lowdebt & pegok).fillna(False)
q1 = (F.roe5_n15 >= 4) & stab
q2 = (F.opm5_n20 >= 4) & stab & gm_st
QB = QB0 & QU
Q1 = QB & q1; Q2 = QB & q2; Q3 = Q1 | Q2
Q3_G = Q3 & UNI
Q3_ALL = QB0 & (q1 | q2)
# ------------------------------------------------------------ settori esclusi
sec = F.sector.fillna('')
GRP = pd.Series(np.select([sec.isin(['Utilities', 'Electric Utilities', 'Multi-Utilities']),
                           sec.isin(['Energy', 'Energy Equipment & Services', 'Oil, Gas & Consumable Fuels']),
                           sec.isin(['Basic Materials', 'Materials', 'Metals & Mining', 'Chemicals']),
                           sec.isin(['Financial Services', 'Financial', 'Financials', 'Capital Markets', 'Diversified Financial Services',
                                     'Regional Banks', 'Banks', 'Insurance']),
                           sec.isin(['Real Estate', 'Equity Real Estate Investment Trusts (REITs)'])],
                          ['Utilities', 'Energia', 'Materie prime', 'Finanza', 'Immobiliare'], ''), index=F.index)
nim = pd.DataFrame({k: F[f'ni_y{k}'] for k in yrs}).mean(axis=1, skipna=False)
roe5m = roe.mean(axis=1, skipna=False)
pbv = (F.mcap / F.equity).where(F.equity > 0)
S_UT = (GRP == 'Utilities') & (F.divy >= 0.03) & (F.de <= 2) & (F.roe >= 0.08) & (F.equity > 0) & (F.divy * F.pe < 1) & (F.pe > 0)
S_EM = GRP.isin(['Energia', 'Materie prime']) & (nim > 0) & (F.mcap / nim <= 12) & (F.de <= 0.5) & (F.equity > 0)
S_FI = (GRP == 'Finanza') & (F.roe >= 0.12) & (roe5m >= 0.10) & (pbv <= 2)
S_RE = (GRP == 'Immobiliare') & (pbv <= 1) & (F.divy >= 0.04) & (F.de <= 1.5)
S_UT, S_EM, S_FI, S_RE = [s.fillna(False) for s in (S_UT, S_EM, S_FI, S_RE)]
S_ALL = S_UT | S_EM | S_FI | S_RE
# ------------------------------------------------------------ regioni
REG = {'Mondo': ALL, 'USA grandi': (F.reg == 'USA') & ~F.us_new, 'USA piccole/medie': F.us_new, 'Europa': F.reg == 'Europa', 'Asia': F.reg == 'Asia'}


def maxdd(r): w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()


def useries(univ):
    return F[univ].groupby('date').r_eur.mean().reindex(REB).fillna(0.0)


def ev(name, m, univ, tag='', r=None):
    """portafoglio dei titoli in m dentro univ contro l'universo univ (senza costi), per periodo"""
    if r is None: r, n = run(F, m & univ)
    else: n = F[m & univ].groupby('date').size().reindex(REB).fillna(0)
    u = useries(univ)
    out = []
    for p, (a, b) in PALL.items():
        ds = [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
        Xp = F[m & univ & (F.date >= a) & (F.date <= b) & F.f12.notna()]
        out.append(dict(gruppo=tag, variante=name, periodo=p, n=n.reindex(ds).mean(), cagr=cagr(r, a, b), univ=cagr(u, a, b),
                        diff=cagr(r, a, b) - cagr(u, a, b), t=tstat((r - u)[ds]), maxdd=maxdd(r[ds]), W5=Xp.W5.mean(), L20=Xp.L20.mean()))
    return out, r


def caso(m, pool, n_it=400, seed=7):
    """quota di estrazioni a caso (stessa numerosita' per data, dentro pool) battute dal portafoglio m, lordo, per periodo"""
    rng = np.random.default_rng(seed); R = F.r_eur.values
    cnt = F[m].groupby('date').size()
    real = F[m].groupby('date').r_eur.mean().reindex(REB).fillna(0.0)
    G = {t: x.index.values for t, x in F[pool].groupby('date')}
    sims = {p: [] for p in PALL}
    for it in range(n_it):
        g = {}
        for t in REB:
            k = cnt.get(t, 0); idx = G.get(t, np.array([]))
            g[t] = R[rng.choice(idx, min(k, len(idx)), replace=False)].mean() if k and len(idx) else 0.0
        g = pd.Series(g)
        for p, (a, b) in PALL.items(): sims[p].append(cagr(g, a, b))
    return {p: np.mean(np.array(sims[p]) < cagr(real, a, b)) for p, (a, b) in PALL.items()}


def fmt(T):
    return T.pivot_table(index=['gruppo', 'variante'], columns='periodo', values=['n', 'cagr', 'diff', 't'], sort=False).round(3)
