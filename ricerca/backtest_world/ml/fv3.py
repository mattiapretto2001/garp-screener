# fv3: definizioni condivise della matrice features_v3 (famiglie, direzioni a priori, periodi) e funzioni di servizio
# per i 5 agenti di ricerca. Uso:  import sys; sys.path.insert(0, '<...>/backtest_world/ml'); import fv3; F = fv3.load()
import os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
PATH = f'{HERE}/features_v3.pkl'

# famiglia -> variabili predittive (tutte point-in-time alla data)
FAMILIES = {
    'VALUTAZIONE': ['pe', 'ey', 'peg', 'ev_ebitda', 'ebit_ev', 'ev_sales', 'fcfy', 'pb'],
    'QUALITA': ['roe', 'roic', 'gpa', 'gm', 'opm', 'npm', 'fcf_m', 'fcf_ni', 'accruals', 'de', 'nd_ebitda', 'cur_ratio',
                'neg_eq', 'n_loss_5y', 'n_loss_10y', 'opm_avg5', 'opm_std5', 'gm_std5', 'revg_std5', 'n_revdown_5y'],
    'CRESCITA': ['revq', 'revg_ttm', 'rev_cagr', 'rev_cagr3', 'rev_cagr5', 'epsg', 'epsq', 'accel_q', 'accel_y', 'oplev',
                 'd_opm', 'd_gm', 'turn_profit'],
    'INVESTIMENTO': ['rd_int', 'sga_int', 'capex_int', 'asset_g', 'dsh1', 'dsh3'],
    'SOPRAVVIVENZA': ['burner', 'cash_mcap', 'burn_mcap', 'runway_y', 'cash_debt', 'netcash_mcap'],
    'PREZZO': ['mom12_1', 'mom6', 'mom3', 'mom1', 'hi52', 'ma200', 'vol1y', 'logmcap', 'log_adv', 'turnover', 'age_y', 'hist_y', 'fin_age_d'],
    'ANALISTI': ['surp_last', 'surp_mean4', 'n_beat4', 'n_est4'],
    'INDUSTRIA': ['ind_n', 'ind_dshare4', 'ind_revg_med', 'ind_revg_agg', 'ind_accel_agg', 'ind_accel_med', 'ind_mom_med', 'ind_mom_pos',
                  'rel_revg_ind', 'rel_mom_ind', 'rel_gm_ind'],
}
PREDICTORS = [c for v in FAMILIES.values() for c in v]
# direzione attesa a priori (letteratura/buon senso), DA VERIFICARE: +1 piu' alto = meglio, -1 piu' basso = meglio, 0 ambigua
DIRECTION = {
    'pe': -1, 'ey': 1, 'peg': -1, 'ev_ebitda': -1, 'ebit_ev': 1, 'ev_sales': -1, 'fcfy': 1, 'pb': -1,
    'roe': 1, 'roic': 1, 'gpa': 1, 'gm': 1, 'opm': 1, 'npm': 1, 'fcf_m': 1, 'fcf_ni': 1, 'accruals': -1, 'de': -1, 'nd_ebitda': -1,
    'cur_ratio': 1, 'neg_eq': -1, 'n_loss_5y': -1, 'n_loss_10y': -1, 'opm_avg5': 1, 'opm_std5': -1, 'gm_std5': -1, 'revg_std5': -1,
    'n_revdown_5y': -1,
    'revq': 1, 'revg_ttm': 1, 'rev_cagr': 1, 'rev_cagr3': 1, 'rev_cagr5': 1, 'epsg': 1, 'epsq': 1, 'accel_q': 1, 'accel_y': 1,
    'oplev': 1, 'd_opm': 1, 'd_gm': 1, 'turn_profit': 1,
    'rd_int': 0, 'sga_int': -1, 'capex_int': 0, 'asset_g': -1, 'dsh1': -1, 'dsh3': -1,
    'burner': -1, 'cash_mcap': 1, 'burn_mcap': -1, 'runway_y': 1, 'cash_debt': 1, 'netcash_mcap': 1,
    'mom12_1': 1, 'mom6': 1, 'mom3': 1, 'mom1': -1, 'hi52': 1, 'ma200': 1, 'vol1y': -1, 'logmcap': 0, 'log_adv': 0, 'turnover': -1,
    'age_y': 1, 'hist_y': 1, 'fin_age_d': -1,
    'surp_last': 1, 'surp_mean4': 1, 'n_beat4': 1, 'n_est4': 0,
    'ind_n': 0, 'ind_dshare4': 0, 'ind_revg_med': 1, 'ind_revg_agg': 1, 'ind_accel_agg': 1, 'ind_accel_med': 1, 'ind_mom_med': 1,
    'ind_mom_pos': 1, 'rel_revg_ind': 1, 'rel_mom_ind': 1, 'rel_gm_ind': 1,
}
TARGETS = ['r', 'r_eur', 'fwd12_loc', 'fwd12_eur', 'xs12_reg', 'rk12_reg', 'rk12', 'top5', 'top5_reg', 'bot20', 'bot20_reg',
           'crash50', 'bankrupt12', 'delist12', 'fwd36_loc', 'fwd36_eur', 'xs36_reg', 'rk36_reg', 'x3']
# MAI come predittori: informazione dal futuro (delisted = esito finale della societa'; us_new = lista costruita con la
# liquidita' 2011-2026) o target. sector/industry sono la classificazione di OGGI (piccola sbirciata, usarle solo come gruppi).
NOT_PREDICTORS = TARGETS + ['delisted', 'us_new', 'ended']
PER3 = {'2012-16': ('2011-12-31', '2016-09-30'), '2017-21': ('2016-12-31', '2021-09-30'), '2022-26': ('2021-12-31', '2026-09-30')}
REG_ROB = ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia', 'Altri']


def load(path=PATH, cols=None):
    F = pd.read_pickle(path)
    return F if cols is None else F[cols]


def xs_rank(F, cols, by='date', signed=False):
    """rango percentile (0-1) dentro ogni data (o gruppo), mancanti restano NaN; signed=True usa DIRECTION (1 = migliore)"""
    out = {}
    for c in cols:
        s = F[c].astype(float)
        if signed and DIRECTION.get(c, 0) < 0: s = -s
        g = s.groupby([F[b] for b in ([by] if isinstance(by, str) else by)])
        out[c] = (g.rank(method='average') - 0.5) / g.transform('count')
    return pd.DataFrame(out, index=F.index)


def winsor(F, cols, q=0.01, by='date'):
    """taglia le code all'1%-99% dentro ogni data"""
    out = {}
    for c in cols:
        g = F[c].astype(float).groupby(F[by])
        lo, hi = g.transform(lambda s: s.quantile(q)), g.transform(lambda s: s.quantile(1 - q))
        out[c] = F[c].clip(lo, hi)
    return pd.DataFrame(out, index=F.index)


def retarget(F, mask, group=('reg', 'date')):
    """ricalcola eccesso/rango/top5/bot20 a 12 mesi dentro un sotto-universo (es. ~F.excl_sector)"""
    X = F[mask & F.fwd12_eur.notna()]
    g = X.groupby(list(group)).fwd12_eur
    rk = (g.rank(method='average') - 0.5) / g.transform('count')
    return pd.DataFrame({'xs12': X.fwd12_eur - g.transform('mean'), 'rk12': rk, 'top5': rk >= 0.95, 'bot20': rk <= 0.20}, index=X.index)


def nw_t(x, lags=4):
    """t di Newey-West della media di una serie temporale (es. coefficienti trimestrali di Fama-MacBeth).
    Con target a 12 mesi e date trimestrali le osservazioni si sovrappongono per 3 trimestri: lags>=3."""
    x = pd.Series(x).dropna().values.astype(float); T = len(x)
    if T < 5: return np.nan
    e = x - x.mean(); v = e @ e / T
    for l in range(1, min(lags, T - 1) + 1): v += 2 * (1 - l / (lags + 1)) * (e[l:] @ e[:-l]) / T
    return x.mean() / np.sqrt(v / T) if v > 0 else np.nan


def walk_forward_splits(dates, first_test_year=2016, embargo_q=4):
    """split annuali: addestra su date <= fine anno t-1 meno embargo (target a 12 mesi sovrapposti), testa sulle date dell'anno t"""
    D = sorted(pd.to_datetime(pd.Series(dates).unique()))
    for y in range(first_test_year, max(D).year + 1):
        test = [d for d in D if d.year == y]
        if not test: continue
        cut = test[0] - pd.offsets.QuarterEnd(embargo_q)
        train = [d for d in D if d <= cut]
        if train: yield y, train, test
