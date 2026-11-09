# profili_common: definizioni FISSATE PRIMA di guardare i risultati dentro i profili (07/11/2026).
# 5 profili con regole d'ingresso semplici, liste di variabili candidate per profilo (economia, non dati),
# funzioni per ranghi dentro profilo, Fama-MacBeth, portafogli top-N e scelte a caso.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
OUT = f'{HERE}/prof_out'; os.makedirs(OUT, exist_ok=True)
COST = 0.005

EMERGING = ['Semiconductors', 'Semiconductor Equipment & Materials', 'Semiconductors & Semiconductor Equipment', 'Solar', 'Uranium',
            'Utilities—Renewable', 'Renewable Energy', 'Independent Power and Renewable Electricity Producers',
            'Electrical Equipment & Parts', 'Aerospace & Defense', 'Biotechnology', 'Biotechnology & Medical Research',
            'Software—Infrastructure', 'Communication Equipment', 'Communications Equipment', 'Computer Hardware',
            'Scientific & Technical Instruments', 'Electronic Components', 'Health Information Services', 'Health Care Technology',
            'Electronic Gaming & Multimedia', 'Diagnostics & Research', 'Internet Content & Information']
COMMOD_SECT = ['Energy', 'Basic Materials', 'Materials', 'Utilities', 'Electric Utilities', 'Multi-Utilities']


def norm_ind(s):
    return (s.astype(str).str.replace('Â', ' ').str.replace(r'\s+', ' ', regex=True).str.strip()
            .str.replace(' - ', '—').str.replace('-', '—'))


def profiles(F):
    """regole d'ingresso ex ante (una societa' puo' stare in piu' profili). Universo di partenza: matrice fv3 (>=300 M$, liquida)."""
    ind = norm_ind(F.industry); sec = F.sector.astype(str)
    fin_re = ind.str.contains('Bank|Insurance|REIT|Real Estate|Mortgage', regex=True) | sec.isin(['Real Estate', 'Equity Real Estate Investment Trusts (REITs)'])
    rev_usd = F.rev_ttm * F.fx_rep
    P = {}
    # 1 qualita' durevole: almeno 5 bilanci annuali, utile in almeno 4 degli ultimi 5 anni, utile TTM >0; no banche/assicurazioni/immobiliare
    P['QUAL'] = (F.n_years >= 5) & (F.n_loss_5y <= 1) & (F.ni_ttm > 0) & ~fin_re
    # 2 GARP: settori GARP, utile TTM >0 e PEG definito (P/E >0 e crescita utile per azione >0)
    P['GARP'] = ~F.excl_sector & (F.ni_ttm > 0) & F.peg.notna()
    # 3 crescita: settori GARP, ricavi TTM +20% sull'anno prima
    P['CRESC'] = ~F.excl_sector & (F.revg_ttm > 0.20)
    # 4 non ancora profittevoli: settori GARP, utile TTM <0, ricavi TTM >50 M$
    P['PREPROF'] = ~F.excl_sector & (F.ni_ttm < 0) & (rev_usd > 50e6)
    # 5 temi: settori esclusi non finanziari (energia, materie prime, servizi pubblici) + industrie 'emergenti' (lista fissa)
    P['TEMI'] = sec.isin(COMMOD_SECT) | ind.isin(EMERGING)
    P = {k: v.fillna(False).astype(bool) for k, v in P.items()}
    return P, ind


# variabili candidate per profilo (scelte per ragionamento economico; ho gia' visto i risultati sull'universo intero degli altri agenti)
CAND = {
    'QUAL': ['roic', 'gpa', 'opm_avg5', 'opm_std5', 'gm_std5', 'revg_std5', 'n_loss_10y', 'fcf_m', 'fcf_ni', 'accruals', 'nd_ebitda',
             'dsh3', 'rev_cagr5', 'fcfy', 'ev_ebitda', 'mom12_1', 'hi52', 'vol1y'],
    'GARP': ['peg', 'pe', 'fcfy', 'ev_sales', 'roe', 'roic', 'fcf_m', 'revq', 'rev_cagr', 'epsq', 'accel_q', 'd_opm', 'dsh3', 'n_beat4',
             'surp_mean4', 'mom12_1', 'hi52', 'vol1y'],
    'CRESC': ['revq', 'revg_ttm', 'rev_cagr3', 'accel_q', 'accel_y', 'gm', 'd_gm', 'd_opm', 'opm', 'fcf_m', 'ev_sales', 'dsh1', 'dsh3',
              'runway_y', 'n_beat4', 'mom12_1', 'hi52', 'vol1y'],
    'PREPROF': ['gm', 'd_gm', 'd_opm', 'opm', 'fcf_m', 'runway_y', 'cash_mcap', 'burn_mcap', 'netcash_mcap', 'dsh1', 'dsh3', 'revq',
                'revg_ttm', 'accel_q', 'ev_sales', 'sga_int', 'mom12_1', 'hi52', 'vol1y'],
    'TEMI': ['ind_revg_agg', 'ind_accel_agg', 'ind_mom_med', 'ind_mom_pos', 'rel_mom_ind', 'rel_revg_ind', 'revq', 'revg_ttm', 'fcfy', 'ey',
             'ev_sales', 'roic', 'fcf_m', 'dsh3', 'netcash_mcap', 'mom12_1', 'hi52', 'vol1y'],
}
PNAME = {'QUAL': 'Qualita durevole', 'GARP': 'GARP', 'CRESC': 'Crescita', 'PREPROF': 'Non ancora profittevoli', 'TEMI': 'Temi'}
TGT = ['rk12_reg', 'top5_reg', 'bot20_reg']
GROUPS = ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia']
OOSP = {'2015-16': (2015, 2016), '2017-21': (2017, 2021), '2022-26': (2022, 2026), '2015-26': (2015, 2026)}


def rank_in(X, cols, date):
    """rango 0-1 per data con segno a priori (1 = meglio secondo DIRECTION); mancanti = 0.5 (neutro)"""
    out = {}
    for c in cols:
        s = X[c].astype(float)
        if fv3.DIRECTION.get(c, 0) < 0: s = -s
        g = s.groupby(date)
        out[c] = ((g.rank(method='average') - 0.5) / g.transform('count')).fillna(0.5).astype('float32')
    return pd.DataFrame(out, index=X.index)


def fm(Z, y, date, cols, min_n=30):
    """Fama-MacBeth: OLS per data di y su Z[cols] (+costante). Ritorna DataFrame data x coef."""
    res = {}
    for d, idx in date.groupby(date).groups.items():
        yy = y.loc[idx]; ok = yy.notna().values
        if ok.sum() < max(min_n, len(cols) + 5): continue
        A = np.column_stack([np.ones(ok.sum()), Z.loc[idx, cols].values[ok]])
        b = np.linalg.lstsq(A, yy.values[ok].astype(float), rcond=None)[0]
        res[d] = b[1:]
    return pd.DataFrame(res, index=cols).T.sort_index()


def ic_series(z, y, date, min_n=30):
    """correlazione per data fra z (rango) e y (rango o 0/1) - per binari e' la point-biserial sui ranghi"""
    D = pd.DataFrame({'z': z, 'y': y.astype(float), 'd': date}).dropna()
    out = {}
    for d, g in D.groupby('d'):
        if len(g) >= min_n and g.y.std() > 0 and g.z.std() > 0: out[d] = np.corrcoef(g.z, g.y.rank())[0, 1]
    return pd.Series(out).sort_index()


def nwt(x, lags=4): return fv3.nw_t(x, lags)


def cagr_q(r):
    r = pd.Series(r).dropna()
    return (1 + r).prod() ** (4 / len(r)) - 1 if len(r) else np.nan


def run_top(X, score, n, col='r_eur'):
    """top-n per data secondo score (dentro X), pesi uguali, costo 0,5% per acquisto/vendita. Ritorna serie trimestrale netta e insiemi"""
    d = X.assign(_s=score).dropna(subset=['_s']).sort_values(['date', '_s'], ascending=[True, False]).groupby('date').head(n)
    REB = sorted(X.date.unique()); G = {t: x for t, x in d.groupby('date')}
    r, prev, picks = {}, set(), {}
    for t in REB:
        x = G.get(t); k = set(x.t) if x is not None else set()
        g = x[col].mean() if x is not None and len(x) else 0.0
        sold = len(prev - k) / len(prev) if prev else 0; bought = len(k - prev) / len(k) if k else 0
        r[t] = g - COST * (sold + bought); prev = k; picks[t] = x.index.values if x is not None else np.array([], int)
    return pd.Series(r).sort_index(), picks


def rand_pct(X, n, real_r, years, n_it=300, seed=11):
    """quota di estrazioni a caso di n titoli per data (dentro X, lorde) battute dal portafoglio reale (netto) nel periodo"""
    rng = np.random.default_rng(seed)
    dates = [d for d in sorted(X.date.unique()) if years[0] <= d.year <= years[1]]
    R = {d: X.loc[X.date == d, 'r_eur'].values for d in dates}
    sims = np.empty(n_it)
    for i in range(n_it):
        rs = [rng.choice(R[d], min(n, len(R[d])), replace=False).mean() for d in dates]
        sims[i] = cagr_q(rs)
    return np.mean(sims < cagr_q(real_r.loc[dates]))


def ic_matrix(Z, y, date, min_n=30):
    ok = y.notna().values
    Z = Z[ok]; y = y[ok].astype(float); date = date[ok]
    y = y.groupby(date).rank()
    Zc = Z - Z.groupby(date).transform('mean'); yc = y - y.groupby(date).transform('mean')
    num = Zc.mul(yc, axis=0).groupby(date).sum()
    den = np.sqrt((Zc ** 2).groupby(date).sum().mul((yc ** 2).groupby(date).sum(), axis=0))
    n = date.groupby(date).size()
    IC = (num / den.replace(0, np.nan))
    return IC[n.reindex(IC.index) >= min_n]
