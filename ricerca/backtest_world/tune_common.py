# Funzioni comuni agli script tune_*: carica il pannello, definisce universo largo (settori inclusi), filtri GARP,
# vincitori/perdenti, motore di portafoglio (come world_05: trimestrale, pesi uguali, 0,5% per operazione, EUR).
import pandas as pd, numpy as np
from world_common import BASE, HOME
TODAY = pd.Timestamp('2026-11-06')
EXCL_S = {'Financial Services', 'Financial', 'Financials', 'Basic Materials', 'Materials', 'Energy', 'Utilities', 'Real Estate',
          'Capital Markets', 'Diversified Financial Services', 'Electric Utilities', 'Energy Equipment & Services',
          'Equity Real Estate Investment Trusts (REITs)', 'Multi-Utilities', 'Regional Banks', 'Banks', 'Insurance',
          'Oil, Gas & Consumable Fuels', 'Metals & Mining', 'Chemicals'}
PERIODS = {'2012-19': ('2011-12-31', '2019-09-30'), '2020-24': ('2019-12-31', '2024-09-30'), '2025-26': ('2024-12-31', '2026-09-30')}
FIX_PENCE = True
FILTERS = ['settore', 'ROE', 'D/E', 'FCF', 'ricavi_q', 'EPS_q', 'PEG', 'CAGR']


def period_of(d):
    for p, (a, b) in PERIODS.items():
        if pd.Timestamp(a) <= d <= pd.Timestamp(b): return p
    return None


def load():
    F = pd.read_pickle(f'{BASE}/res/feat.pkl')
    E = pd.read_pickle(f'{BASE}/res/tune_extra.pkl')
    W = pd.read_pickle(f'{BASE}/res/tune_fwd.pkl')
    F = F.merge(E, on=['t', 'date'], how='left').merge(W, on=['t', 'date'], how='left')
    # CORREZIONE (06/11): i prezzi di Londra sono in pence (GBX). world_05 li convertiva come sterline: capitalizzazione
    # e P/E 100 volte troppo alti, quindi quasi nessuna societa' londinese superava il PEG. Qui si divide per 100.
    F['fix_pence'] = F.cur_px.isin(['GBX', 'GBp', 'ZAC', 'ILA'])
    if FIX_PENCE:
        k = np.where(F.fix_pence, 0.01, 1.0)
        F['mcap_usd'] = F.mcap_usd * k; F['mcap'] = F.mcap * k
        F['pe'] = F.mcap / F.ni_ttm; F['peg'] = F.pe / (F.epsg * 100); F['fcfy'] = F.fcf_ttm / F.mcap
    homeok = pd.Series([(c in HOME[e]) if HOME[e] else True for c, e in zip(F.country, F.ex)], index=F.index)
    base = (~F.name.fillna('').str.contains(r'\bCDR\b') & (homeok | F.country.isna()) & F.liq & (F.mcap_usd >= 300e6) & (F.rev_ttm > 0)).fillna(False)
    F = F[base].copy()
    F['excl_sector'] = F.sector.isin(EXCL_S)
    F['per'] = F.date.map(period_of)
    F['reg'] = F.region.replace({'Canada': 'Altri', 'Australia': 'Altri'})
    # metriche nuove
    F['revg_ttm'] = np.where(F.rev_ttm4 > 0, F.rev_ttm / F.rev_ttm4 - 1, np.nan)
    F['revg_ttm_prev'] = np.where(F.rev_ttm8 > 0, F.rev_ttm4 / F.rev_ttm8 - 1, np.nan)
    F['accel_q'] = F.revq - F.revq_prev
    F['accel_y'] = F.revg_ttm - F.revg_ttm_prev
    F['opm'] = F.opi_ttm / F.rev_ttm
    F['opm4'] = F.opi_ttm4 / F.rev_ttm4
    F['d_opm'] = F.opm - F.opm4
    F['oplev'] = np.where(F.opi_ttm4 > 0, F.opi_ttm / F.opi_ttm4 - 1, np.nan) - F.revg_ttm
    F['npm'] = F.ni_ttm / F.rev_ttm
    F['fcf_ni'] = np.where(F.ni_ttm > 0, F.fcf_ttm / F.ni_ttm, np.nan)
    F['fcf_m'] = F.fcf_ttm / F.rev_ttm
    shr = F.sh0 / F.sh4
    F['dshares'] = np.where(shr.between(0.5, 2), shr - 1, np.nan)
    F['first_profit'] = (F.ni_ttm > 0) & (F.ni_ttm4 <= 0)
    F['first_profit_y'] = (F.ni_ttm > 0) & (F.n_prof_y == 0)
    F['logmcap'] = np.log10(F.mcap_usd)
    F['ps'] = F.mcap / F.rev_ttm
    F = F.replace([np.inf, -np.inf], np.nan)
    # filtri GARP: True = superato. Dato mancante = non superato (come lo screener), segnato a parte
    F['ok_settore'] = ~F.excl_sector
    F['ok_ROE'] = ((F.ni_ttm > 0) & (F.equity > 0) & (F.roe > 0.15)).fillna(False)
    F['ok_D/E'] = ((F.equity > 0) & (F.de < 1)).fillna(False)
    F['ok_FCF'] = (F.fcf_ttm > 0).fillna(False)
    F['ok_ricavi_q'] = (F.revq > 0.05).fillna(False)
    F['ok_EPS_q'] = (F.epsq > 0.05).fillna(False)
    F['ok_PEG'] = ((F.ni_ttm > 0) & (F.epsg > 0) & (F.peg > 0) & (F.peg < 2)).fillna(False)
    F['ok_CAGR'] = (F.rev_cagr > 0.10).fillna(False)
    F['na_ROE'] = F.roe.isna() | F.equity.isna(); F['na_D/E'] = F.de.isna(); F['na_FCF'] = F.fcf_ttm.isna()
    F['na_ricavi_q'] = F.revq.isna(); F['na_EPS_q'] = F.epsq.isna() & (F.ni_q > 0); F['na_PEG'] = F.peg.isna() & (F.ni_ttm > 0) & (F.epsg > 0)
    F['na_CAGR'] = F.rev_cagr.isna(); F['na_settore'] = False
    ok = F[[f'ok_{f}' for f in FILTERS]]
    F['n_fail'] = (~ok).sum(axis=1)
    F['GARP'] = F.n_fail == 0
    # vincitori e perdenti (rendimento futuro in valuta locale, societa' uscite incluse)
    g = F.groupby('date').f12
    F['pct12'] = g.rank(pct=True)
    F['W5'] = (F.pct12 >= 0.95) & F.f12.notna()
    F['W10'] = (F.pct12 >= 0.90) & F.f12.notna()
    F['L20'] = (F.pct12 <= 0.20) & F.f12.notna()
    F['L50'] = (F.f12 <= -0.5) & F.f12.notna()
    F['MB3'] = (F.f36 >= 2.0) & F.f36.notna()
    return F


# ------------------------------------------------------------------ motore portafoglio
COST = 0.005


def run(F, mask, col='r_eur', topn=None, score=None):
    """rendimento netto trimestrale di un portafoglio a pesi uguali dei titoli in mask (ribilanciato ogni trimestre)"""
    d = F[mask]
    if topn is not None:
        d = d.assign(_s=score[mask]).sort_values(['date', '_s'], ascending=[True, False]).groupby('date').head(topn)
    REB = sorted(F.date.unique())
    G = {t: x for t, x in d.groupby('date')}
    r, n, prev = {}, {}, set()
    for i, t in enumerate(REB):
        x = G.get(t)
        k = set(x.t) if x is not None else set()
        g = x[col].mean() if x is not None and len(x) else 0.0
        sold = len(prev - k) / len(prev) if prev else 0
        bought = len(k - prev) / len(k) if k else 0
        r[t] = g - COST * (sold + bought); n[t] = len(k); prev = k
    return pd.Series(r), pd.Series(n)


def nextd(t, REB):
    i = REB.index(t); return REB[i + 1] if i + 1 < len(REB) else TODAY


def cagr(r, a, b):
    REB = list(r.index)
    ds = [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]
    if not ds: return np.nan
    yrs = (nextd(ds[-1], REB) - ds[0]).days / 365.25
    return (1 + r[ds]).prod() ** (1 / yrs) - 1


def tstat(x):
    x = pd.Series(x).dropna()
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else np.nan


def pr(a, d=1):
    return '' if pd.isna(a) else f'{a * 100:+.{d}f}%'.replace('.', ',')


# ------------------------------------------------------------------ filtri parametrici e punteggio dello screener
BASE_P = dict(settore=True, roe=0.15, de=1.0, fcf=True, revq=0.05, epsq=0.05, peg=2.0, cagr=0.10)


def mask(F, p):
    m = pd.Series(True, index=F.index)
    if p['settore']: m &= ~F.excl_sector
    if p['roe'] is not None: m &= ((F.ni_ttm > 0) & (F.equity > 0) & (F.roe > p['roe'])).fillna(False)
    if p['de'] is not None: m &= ((F.equity > 0) & (F.de < p['de'])).fillna(False)
    if p['fcf']: m &= (F.fcf_ttm > 0).fillna(False)
    if p['revq'] is not None: m &= (F.revq > p['revq']).fillna(False)
    if p['epsq'] is not None: m &= (F.epsq > p['epsq']).fillna(False)
    if p['peg'] is not None: m &= ((F.ni_ttm > 0) & (F.epsg > 0) & (F.peg > 0) & (F.peg < p['peg'])).fillna(False)
    if p['cagr'] is not None: m &= (F.rev_cagr > p['cagr']).fillna(False)
    return m


def pct(s, higher=True):
    n = s.notna().sum()
    p = (s.rank(method='average') - 0.5) / n if n else s * np.nan
    return (p if higher else 1 - p).fillna(0.5)


W0 = {'peg': 30, 'revq': 12, 'epsq': 12, 'rev_cagr': 12, 'roe': 12, 'fcfy': 11, 'de': 11}
LOW = {'peg', 'de'}


def score(F, m, W=W0):
    out = pd.Series(np.nan, index=F.index)
    for t, x in F[m].groupby('date'):
        out[x.index] = sum(w * pct(x[k], k not in LOW) for k, w in W.items())
    return out


