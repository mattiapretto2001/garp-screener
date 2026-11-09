# funzioni comuni agli script regressioni_*.py
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3
HERE = fv3.HERE
S12 = np.sqrt(12)

# Rappresentanti scelti PRIMA di guardare i rendimenti (regressioni_00: cluster |rho|>0.5):
# regola = copertura piu' alta, poi centralita'; 2 rappresentanti solo dove il cluster mescola due concetti
# (momentum: mom12_1 + hi52 usato dal core; flusso di cassa: fcfy valutazione + fcf_m margine).
# Esclusi dal blocco mondiale i campi estesi scelti ex post fuori dagli USA (gm, gpa, cur_ratio, rd_int, sga_int,
# sorprese, n_est4, age_y, accel_q con copertura europea 53%): vanno nel blocco solo-USA.
GLOBAL = ['ey', 'ev_sales', 'pb', 'fcfy',                         # valutazione
          'roe', 'opm_avg5', 'fcf_m', 'accruals', 'netcash_mcap', 'neg_eq', 'n_loss_5y', 'opm_std5', 'revg_std5',  # qualita'
          'revq', 'rev_cagr', 'accel_y', 'd_opm', 'epsg', 'epsq', 'turn_profit',                      # crescita
          'asset_g', 'dsh1', 'capex_int', 'cash_mcap',                                                 # investimento/sopravv.
          'mom12_1', 'hi52', 'mom1', 'vol1y', 'logmcap', 'turnover', 'hist_y', 'fin_age_d',          # prezzo/mercato
          'ind_n', 'ind_dshare4', 'ind_revg_med', 'ind_accel_agg', 'ind_mom_med']                      # industria
USBLOCK = ['gpa', 'gm', 'cur_ratio', 'rd_int', 'sga_int', 'accel_q', 'n_beat4', 'surp_mean4', 'n_est4', 'age_y']
FAM = {v: f for f, vs in fv3.FAMILIES.items() for v in vs}
LAB = {  # etichette italiane brevi
    'ey': 'Rend. utili (E/P)', 'ev_sales': 'EV/ricavi', 'pb': 'P/patrimonio', 'fcfy': 'Rend. FCF (FCF/cap.)', 'pe': 'P/E', 'peg': 'PEG',
    'ev_ebitda': 'EV/EBITDA', 'ebit_ev': 'EBIT/EV',
    'roe': 'ROE', 'roic': 'ROIC', 'opm_avg5': 'Margine op. medio 5a', 'opm': 'Margine op.', 'npm': 'Margine netto', 'fcf_m': 'Margine FCF',
    'fcf_ni': 'FCF/utile', 'accruals': 'Accantonamenti (accruals)', 'netcash_mcap': 'Cassa netta/cap.', 'de': 'Debito/patrimonio',
    'nd_ebitda': 'Debito netto/EBITDA', 'cash_debt': 'Cassa/debito',
    'neg_eq': 'Patrimonio negativo', 'n_loss_5y': 'Anni in perdita (5)', 'n_loss_10y': 'Anni in perdita (10)', 'opm_std5': 'Instabilita margine op.',
    'revg_std5': 'Instabilita crescita ricavi', 'n_revdown_5y': 'Anni ricavi in calo', 'gm_std5': 'Instabilita margine lordo',
    'revq': 'Ricavi trimestre a/a', 'revg_ttm': 'Ricavi 12m a/a', 'rev_cagr': 'CAGR ricavi 4a', 'rev_cagr3': 'CAGR ricavi 3a', 'rev_cagr5': 'CAGR ricavi 5a',
    'accel_y': 'Accelerazione ricavi (anno)', 'accel_q': 'Accelerazione ricavi (trim.)', 'd_opm': 'Var. margine op.', 'oplev': 'Leva operativa',
    'd_gm': 'Var. margine lordo', 'epsg': 'Crescita EPS 12m', 'epsq': 'Crescita EPS trim.', 'turn_profit': 'Svolta all utile',
    'asset_g': 'Crescita attivo', 'dsh1': 'Diluizione 1a', 'dsh3': 'Diluizione 3a', 'capex_int': 'Capex/ricavi', 'rd_int': 'R&S/ricavi',
    'sga_int': 'Spese gen./ricavi', 'cash_mcap': 'Cassa/cap.', 'burner': 'Brucia cassa', 'burn_mcap': 'Cassa bruciata/cap.', 'runway_y': 'Autonomia (anni)',
    'mom12_1': 'Momentum 12-1', 'hi52': 'Prezzo/max 52 sett.', 'mom1': 'Rend. ultimo mese', 'mom3': 'Momentum 3m', 'mom6': 'Momentum 6m', 'ma200': 'Prezzo/media 200',
    'vol1y': 'Volatilita 1a', 'logmcap': 'Capitalizzazione (log)', 'log_adv': 'Scambi (log)', 'turnover': 'Rotazione scambi', 'hist_y': 'Anni di storia bilanci',
    'age_y': 'Anni dalla quotazione', 'fin_age_d': 'Eta del bilancio (giorni)', 'ind_n': 'N. societa industria', 'ind_dshare4': 'Var. peso industria',
    'ind_revg_med': 'Crescita ricavi industria', 'ind_revg_agg': 'Crescita aggr. industria', 'ind_accel_agg': 'Accelerazione industria',
    'ind_accel_med': 'Accel. mediana industria', 'ind_mom_med': 'Momentum industria', 'ind_mom_pos': 'Quota industria in rialzo',
    'rel_revg_ind': 'Crescita vs industria', 'rel_mom_ind': 'Momentum vs industria', 'rel_gm_ind': 'Margine lordo vs industria',
    'gpa': 'Utile lordo/attivo', 'gm': 'Margine lordo', 'cur_ratio': 'Liquidita corrente', 'n_beat4': 'Battute stime (4)',
    'surp_mean4': 'Sorpresa media (4)', 'surp_last': 'Ultima sorpresa', 'n_est4': 'Copertura analisti', 'cash_debt': 'Cassa/debito'}


def load(cols=None):
    M = pd.read_pickle(f'{HERE}/reg_Z.pkl')
    return M


def rank_z(df, cols, by, signed=False):
    """ranghi per gruppo -> z con varianza 1 (mancanti NaN)"""
    out = {}
    keys = [df[b] for b in by]
    for c in cols:
        s = df[c].astype(float)
        if signed and fv3.DIRECTION.get(c, 0) < 0: s = -s
        g = s.groupby(keys)
        out[c] = ((g.rank(method='average') - 0.5) / g.transform('count') - 0.5) * S12
    return pd.DataFrame(out, index=df.index)


def fm(df, xcols, ycol, min_n=None):
    """Fama-MacBeth: OLS per data. df deve avere date, xcols (z, NaN->0), ycol. Ritorna coef per data (DataFrame)."""
    min_n = min_n or (len(xcols) + 20)
    rows = {}
    for d, g in df.groupby('date', sort=True):
        g = g[g[ycol].notna()]
        if len(g) < min_n: continue
        X = np.column_stack([np.ones(len(g)), g[xcols].fillna(0).values.astype(float)])
        y = g[ycol].values.astype(float)
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        rows[d] = b[1:]
    return pd.DataFrame(rows, index=xcols).T


def summarize(C, lags=4, per=None):
    """media, t NW per colonna; per = Series data->periodo per le medie di periodo"""
    out = pd.DataFrame({'coef': C.mean(), 't': C.apply(lambda s: fv3.nw_t(s, lags))})
    if per is not None:
        for p in sorted(set(per.values)):
            idx = [d for d in C.index if per.get(d) == p]
            out[p] = C.loc[idx].mean()
            out['t_' + p] = C.loc[idx].apply(lambda s: fv3.nw_t(s, lags))
    return out


def holm(t):
    """p bilaterali (normale) e correzione di Holm"""
    from scipy.stats import norm
    p = 2 * norm.sf(np.abs(np.asarray(t, float)))
    o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0
    for k, i in enumerate(o):
        run = max(run, (m - k) * p[i]); adj[i] = min(1, run)
    return p, adj


def per_of(dates):
    d = pd.to_datetime(pd.Series(sorted(set(dates))))
    lab = {}
    for k, (a, b) in fv3.PER3.items():
        for x in d[(d >= a) & (d <= b)]: lab[x] = k
    return pd.Series(lab)


def vif(X):
    X = np.asarray(X, float); X = (X - X.mean(0)) / X.std(0)
    C = np.corrcoef(X, rowvar=False)
    return np.diag(np.linalg.pinv(C))


def perlab(d):
    y = pd.Timestamp(d).year
    return '2015-16' if y <= 2016 else ('2017-21' if y <= 2021 else '2022-26')


def port(M, sel_fn, dates):
    """portafoglio trimestrale a pesi uguali, r_eur del trimestre dopo, costo 0,5% per acquisto/vendita"""
    prev = pd.Series(dtype=float); rows = []
    for d in dates:
        g = M[M.date == d]; s = sel_fn(g)
        if len(s) == 0:
            rows.append((d, 0.0, 0.0, 0, np.nan, np.nan, np.nan)); prev = pd.Series(dtype=float); continue
        w = pd.Series(1 / len(s), index=s.t.values)
        dw = w.subtract(prev, fill_value=0).abs().sum()
        rows.append((d, s.r_eur.mean() - 0.005 * dw, dw, len(s), s.top5_reg.mean(), s.bot20_reg.mean(), s.crash50.mean()))
        prev = w * (1 + s.set_index('t').r_eur.reindex(w.index).fillna(0)); prev = prev / prev.sum()
    return pd.DataFrame(rows, columns=['date', 'r', 'turn', 'n', 'top5', 'bot20', 'crash']).set_index('date')


def pstats(df, bench):
    r = df.r; b = bench.reindex(r.index)
    out = {'titoli': df.n.mean(), 'CAGR': (1 + r).prod() ** (4 / len(r)) - 1}
    out['diff'] = out['CAGR'] - ((1 + b).prod() ** (4 / len(b)) - 1)
    out['t'] = fv3.nw_t(r - b, 2)
    for p in ['2015-16', '2017-21', '2022-26']:
        m = np.array([perlab(d) == p for d in r.index])
        out[p] = (1 + r[m]).prod() ** (4 / m.sum()) - 1 - ((1 + b[m]).prod() ** (4 / m.sum()) - 1)
    cum = (1 + r).cumprod(); out['perdita_max'] = (cum / cum.cummax() - 1).min()
    out['top5'] = df.top5.mean(); out['bot20'] = df.bot20.mean(); out['crash50'] = df.crash.mean()
    return out
