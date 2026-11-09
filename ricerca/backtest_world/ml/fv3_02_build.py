# fv3_02 (07/11): costruisce ml/features_v3.pkl = res/panel2.pkl (universo, pence corretti, doppioni tolti, liquidita' alla data)
# + variabili in piu' di fv3_01 (bilanci point-in-time) + aggregati per industria + target in EUR e in valuta locale.
import os, sys, pickle, warnings, pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); BT = os.path.dirname(HERE); sys.path.insert(0, BT); sys.path.insert(0, HERE)
from world_common import BASE
import fv3
warnings.filterwarnings('ignore')
TODAY = pd.Timestamp('2026-11-06')
P = pd.read_pickle(f'{BASE}/res/panel2.pkl').reset_index(drop=True)
X = pd.read_pickle(f'{HERE}/fv3_extra.pkl')
assert not X.duplicated(['t', 'date']).any() and not P.duplicated(['t', 'date']).any()
# le colonne ricalcolate da fv3_01 (stessa regola, bilanci fund2 aggiornati) sostituiscono quelle del pannello
REPL = ['gp_ttm', 'rd_ttm', 'sga_ttm', 'gp_ttm4', 'rev_ttm4b', 'cur_a', 'cur_l', 'surp_last', 'surp_mean4', 'n_beat4', 'n_est4', 'age_y']
F = P.drop(columns=REPL).merge(X, on=['t', 'date'], how='left', validate='1:1')
bad = F.m0 != F.m0x                      # bilancio aggiornato in fund2 dopo il pannello: extra non coerenti, si tolgono
print('righe con periodo di bilancio diverso dal pannello:', int(bad.sum()))
FUNDX = [c for c in X.columns if c not in ('t', 'date', 'adv_loc', 'mom1', 'mom3', 'age_y', 'hist_y', 'surp_last', 'surp_mean4', 'n_beat4', 'n_est4')]
F.loc[bad, [c for c in FUNDX if c not in ('m0x', 'fin_end', 'fin_av')]] = np.nan
F.loc[bad, 'fin_av'] = pd.NaT
F.loc[bad, 'fin_end'] = F.loc[bad, 'm0'].map(lambda m: pd.Timestamp(year=m // 12, month=m % 12 + 1, day=1) + pd.offsets.MonthEnd(0))
REB = sorted(F.date.unique()); IDX = {d: i for i, d in enumerate(REB)}
# valori di bilancio impossibili (errori EODHD): mancanti
for c in ['cash', 'debt', 'cur_a', 'cur_l', 'capex_ttm']: F.loc[F[c] < 0, c] = np.nan
for c in ['ta', 'ta4']: F.loc[F[c] <= 0, c] = np.nan
nan = np.nan


def safe_div(a, b, pos_den=True):
    a, b = a.astype(float), b.astype(float)
    ok = (b > 0) if pos_den else (b != 0)
    return (a / b).where(ok)


# ------------------------------------------------------------------ VALUTAZIONE (mcap e bilanci nella valuta di bilancio)
cash0, debt0 = F.cash.fillna(0.0), F.debt.fillna(0.0)
F['ev'] = F.mcap + debt0 - cash0
F['pe'] = safe_div(F.mcap, F.ni_ttm)
F['ey'] = safe_div(F.ni_ttm, F.mcap)
peg = F.pe / (F.epsg * 100)
F['peg'] = peg.where((F.pe > 0) & (F.epsg > 0) & (peg >= 0.05))         # guardia: PEG <0,05 = dato mancante
F['ev_ebitda'] = (F.ev / F.ebitda_ttm).where((F.ebitda_ttm > 0) & (F.ev > 0))
F['ebit_ev'] = safe_div(F.opi_ttm, F.ev)
F['ev_sales'] = (F.ev / F.rev_ttm).where((F.ev > 0) & (F.rev_ttm > 0))
F['fcfy'] = safe_div(F.fcf_ttm, F.mcap)
F['pb'] = safe_div(F.mcap, F.equity)
# ------------------------------------------------------------------ QUALITA'
F['roe'] = safe_div(F.ni_ttm, F.equity)
ic = F.equity + debt0 - cash0
F['roic'] = (F.opi_ttm * 0.75 / ic).where(ic > 0)
F['gpa'] = safe_div(F.gp_ttm, F.ta)
F['gm'] = safe_div(F.gp_ttm, F.rev_ttm).where(lambda s: s.between(-1, 0.999))
F['gm4'] = safe_div(F.gp_ttm4, F.rev_ttm4b).where(lambda s: s.between(-1, 0.999))
F['opm'] = safe_div(F.opi_ttm, F.rev_ttm); F['opm4'] = safe_div(F.opi_ttm4, F.rev_ttm4)
F['npm'] = safe_div(F.ni_ttm, F.rev_ttm)
F['fcf_m'] = safe_div(F.fcf_ttm, F.rev_ttm)
F['fcf_ni'] = safe_div(F.fcf_ttm, F.ni_ttm)
F['accruals'] = safe_div(F.ni_ttm - F.cfo_ttm, F.ta)
F['de'] = safe_div(F.debt, F.equity)
F['nd_ebitda'] = safe_div(debt0 - cash0, F.ebitda_ttm).where(F.debt.notna() | F.cash.notna())
F['cur_ratio'] = safe_div(F.cur_a, F.cur_l)
F['neg_eq'] = (F.equity <= 0).astype(float).where(F.equity.notna())
# ------------------------------------------------------------------ CRESCITA
F['revg_ttm'] = safe_div(F.rev_ttm, F.rev_ttm4) - 1
F['revg_ttm_prev'] = safe_div(F.rev_ttm4, F.rev_ttm8) - 1
F['accel_q'] = F.revq - F.revq_prev
F['accel_y'] = F.revg_ttm - F.revg_ttm_prev
F['oplev'] = (safe_div(F.opi_ttm, F.opi_ttm4) - 1) - F.revg_ttm
F['d_opm'] = F.opm - F.opm4
F['d_gm'] = F.gm - F.gm4
F['turn_profit'] = ((F.ni_ttm > 0) & (F.ni_ttm4 <= 0)).astype(float).where(F.ni_ttm.notna() & F.ni_ttm4.notna())
# ------------------------------------------------------------------ INVESTIMENTO E CAPITALE
F['rd_int'] = safe_div(F.rd_ttm, F.rev_ttm)
F['sga_int'] = safe_div(F.sga_ttm, F.rev_ttm)
F['capex_int'] = safe_div(F.capex_ttm, F.rev_ttm)
F['asset_g'] = safe_div(F.ta, F.ta4) - 1
# ------------------------------------------------------------------ SOPRAVVIVENZA
F['burner'] = (F.fcf_ttm < 0).astype(float).where(F.fcf_ttm.notna())
burn = (-F.fcf_ttm).clip(lower=0)
F['cash_mcap'] = safe_div(F.cash, F.mcap)
F['burn_mcap'] = safe_div(burn, F.mcap)
F['runway_y'] = (F.cash / burn).where(burn > 0).clip(upper=10)
F.loc[(F.fcf_ttm >= 0) & F.cash.notna(), 'runway_y'] = 10.0                 # nessun consumo di cassa = 10 anni (tetto)
F['cash_debt'] = (F.cash / F.debt).where(F.debt > 0).clip(upper=10)
F.loc[(F.debt <= 0) & F.cash.notna(), 'cash_debt'] = 10.0
F['netcash_mcap'] = safe_div(cash0 - debt0, F.mcap).where(F.cash.notna() | F.debt.notna())
# ------------------------------------------------------------------ PREZZO E MERCATO
F['adv_usd'] = F.adv_loc * F.fx_px
F['log_adv'] = np.log10(F.adv_usd.where(F.adv_usd > 0))
F['turnover'] = safe_div(F.adv_usd, F.mcap_usd)
F['logmcap'] = np.log10(F.mcap_usd)
F['fin_age_d'] = (F.date - F.fin_end).dt.days.astype(float)
# ------------------------------------------------------------------ CONTESTO
SECN = {'Financials': 'Financial Services', 'Financial': 'Financial Services', 'Information Technology': 'Technology', 'Materials': 'Basic Materials',
        'Consumer Discretionary': 'Consumer Cyclical', 'Health Care': 'Healthcare', 'Consumer Staples': 'Consumer Defensive',
        'Consumer Non-Cyclicals': 'Consumer Defensive', 'Electric Utilities': 'Utilities', 'Multi-Utilities': 'Utilities',
        'Equity Real Estate Investment Trusts (REITs)': 'Real Estate', 'Regional Banks': 'Financial Services', 'Capital Markets': 'Financial Services',
        'Diversified Financial Services': 'Financial Services', 'IT Services': 'Technology', 'Consumer Goods': 'Consumer Defensive',
        'Industrial Goods': 'Industrials', 'Road & Rail': 'Industrials', 'Internet & Direct Marketing Retail': 'Consumer Cyclical',
        'Services': 'Industrials', 'Academic & Educational Services': 'Consumer Defensive'}
F['sector_n'] = F.sector.replace(SECN)
F['per3'] = None
for p, (a, b) in fv3.PER3.items(): F.loc[(F.date >= a) & (F.date <= b), 'per3'] = p
usr = F[F.reg == 'USA'].groupby('date').mcap_usd.rank(ascending=False, method='first')
F['reg_rob'] = F.reg.replace({'USA': 'USA piccole/medie'})
F.loc[usr[usr <= 500].index, 'reg_rob'] = 'USA grandi'
F2K = pickle.load(open(f'{BASE}/fund/fund2.pkl', 'rb'))
EXT = {k for k, v in F2K.items() if v and 'earn' in v}; del F2K
F['ext_fields'] = F.t.isin(EXT)    # campi estesi (margine lordo, R&S, spese generali, attivo/passivo corrente, sorprese): fuori USA scelti ex post
F['core'] = F.GARP & (F.revq > 0.20).fillna(False) & (F.hi52 >= 0.8).fillna(False) & (F.mcap_usd >= 2e9)
# ------------------------------------------------------------------ INDUSTRIA (globale, tutte le regioni, a ogni data)
F['_ind'] = F.industry.where(~F.industry.isin(['Other', '', 'N/A']) & F.industry.notna())
F['_ru'], F['_ru4'], F['_ru8'] = F.rev_ttm * F.fx_rep, F.rev_ttm4 * F.fx_rep, F.rev_ttm8 * F.fx_rep
G = F.groupby(['_ind', 'date'])
F['ind_n'] = G.t.transform('count').astype(float)
tot = F.groupby('date').t.transform('count')
share = F.ind_n / tot
sh_tab = pd.Series(share.values, index=pd.MultiIndex.from_arrays([F._ind, F.date])).groupby(level=[0, 1]).first()
prev = pd.MultiIndex.from_arrays([F._ind, F.date.map(lambda d: REB[IDX[d] - 4] if IDX[d] >= 4 else pd.NaT)])
F['ind_dshare4'] = share.values / sh_tab.reindex(prev).values - 1
F['ind_revg_med'] = G.revg_ttm.transform('median')
F['ind_accel_med'] = G.accel_y.transform('median')
F['ind_mom_med'] = G.mom12_1.transform('median')
F['ind_mom_pos'] = G.mom12_1.transform(lambda s: (s > 0).sum() / s.notna().sum() if s.notna().sum() else nan)
m1 = F._ru4 > 0
a1 = F._ru.where(m1 & F._ru.notna()); b1 = F._ru4.where(m1 & F._ru.notna())
F['ind_revg_agg'] = a1.groupby([F._ind, F.date]).transform('sum') / b1.groupby([F._ind, F.date]).transform('sum') - 1
m2 = (F._ru4 > 0) & (F._ru8 > 0) & F._ru.notna()
g_now = F._ru.where(m2).groupby([F._ind, F.date]).transform('sum') / F._ru4.where(m2).groupby([F._ind, F.date]).transform('sum') - 1
g_prev = F._ru4.where(m2).groupby([F._ind, F.date]).transform('sum') / F._ru8.where(m2).groupby([F._ind, F.date]).transform('sum') - 1
F['ind_accel_agg'] = g_now - g_prev
F['rel_revg_ind'] = F.revg_ttm - F.ind_revg_med
F['rel_mom_ind'] = (G.mom12_1.rank(method='average') - 0.5) / G.mom12_1.transform('count')
F['rel_gm_ind'] = F.gm - G.gm.transform('median')
small = (F.ind_n < 5) | F._ind.isna()
for c in ['ind_dshare4', 'ind_revg_med', 'ind_accel_med', 'ind_mom_med', 'ind_mom_pos', 'ind_revg_agg', 'ind_accel_agg', 'rel_revg_ind',
          'rel_mom_ind', 'rel_gm_ind']:
    F.loc[small, c] = nan
F.loc[F._ind.isna(), 'ind_n'] = nan
# ------------------------------------------------------------------ TARGET (rendimenti trimestrali di world_04: uscite incluse, fallimento -100%)
RQ = pd.read_pickle(f'{BASE}/res/rq2.pkl').drop_duplicates(['t', 'date'])
RQ = RQ[RQ.t.isin(set(F.t))]
FX = pd.read_pickle(f'{BASE}/eod/fx.pkl').sort_index().ffill()
NEXT = {t: (REB[i + 1] if i + 1 < len(REB) else TODAY) for i, t in enumerate(REB)}


def fx_at(c, t):
    c = {'GBX': 'GBP', 'GBp': 'GBP', 'ZAC': 'ZAR', 'ILA': 'ILS'}.get(c, c)
    if c not in FX.columns: return nan
    i = FX.index.searchsorted(t, side='right') - 1; return FX[c].iloc[max(i, 0)]


curpx = F.drop_duplicates('t').set_index('t').cur_px
cur_e = {}
for c in curpx.dropna().unique():
    for t in REB:
        a = fx_at(c, t) / fx_at('EUR', t); b = fx_at(c, NEXT[t]) / fx_at('EUR', NEXT[t]); cur_e[(c, t)] = b / a - 1
RQ['cur'] = RQ.t.map(curpx)
RQ['r_e'] = (1 + RQ.r) * (1 + np.array([cur_e.get((c, t), nan) for c, t in zip(RQ.cur, RQ.date)])) - 1
tick = sorted(F.t.unique()); TI = {t: i for i, t in enumerate(tick)}
nT, nD = len(tick), len(REB)
Rl = np.zeros((nT, nD)); Re = np.zeros((nT, nD)); BK = np.zeros((nT, nD), bool); EN = np.zeros((nT, nD), bool)
ii = RQ.t.map(TI).values; jj = RQ.date.map(IDX).values
ok = ~pd.isna(jj); ii, jj = ii[ok].astype(int), jj[ok].astype(int)
Rl[ii, jj] = RQ.r.values[ok]; Re[ii, jj] = np.nan_to_num(RQ.r_e.values[ok], nan=0.0)
BK[ii, jj] = RQ.r.values[ok] <= -0.999; EN[ii, jj] = RQ.ended.values[ok]


def fwdk(M, k):
    out = np.full((nT, nD), nan)
    for i in range(nD):
        if i + k >= nD: break          # orizzonte non ancora completo (l'ultimo trimestre arriva solo a oggi)
        out[:, i] = np.prod(1 + M[:, i:i + k], axis=1) - 1
    return out


def anyk(M, k):
    out = np.zeros((nT, nD)); out[:] = nan
    for i in range(nD):
        if i + k >= nD: break
        out[:, i] = M[:, i:i + k].any(axis=1)
    return out


fi, fj = F.t.map(TI).values, F.date.map(IDX).values
F['fwd12_loc'] = fwdk(Rl, 4)[fi, fj]; F['fwd12_eur'] = fwdk(Re, 4)[fi, fj]
F['fwd36_loc'] = fwdk(Rl, 12)[fi, fj]; F['fwd36_eur'] = fwdk(Re, 12)[fi, fj]
F['bankrupt12'] = anyk(BK, 4)[fi, fj]; F['delist12'] = anyk(EN, 4)[fi, fj]
chk = F[['f12', 'fwd12_loc']].dropna()
print('controllo f12 pannello = fwd12_loc:', np.isclose(chk.f12, chk.fwd12_loc, atol=1e-6).mean(), len(chk))
v = F.fwd12_eur.notna()
g = F[v].groupby(['reg', 'date']).fwd12_eur
F.loc[v, 'xs12_reg'] = F.fwd12_eur[v] - g.transform('mean')
F.loc[v, 'rk12_reg'] = (g.rank(method='average') - 0.5) / g.transform('count')
g0 = F[v].groupby('date').fwd12_eur
F.loc[v, 'rk12'] = (g0.rank(method='average') - 0.5) / g0.transform('count')
for c, src, cond in [('top5', 'rk12', lambda s: s >= 0.95), ('top5_reg', 'rk12_reg', lambda s: s >= 0.95),
                     ('bot20', 'rk12', lambda s: s <= 0.20), ('bot20_reg', 'rk12_reg', lambda s: s <= 0.20)]:
    F[c] = cond(F[src]).astype(float).where(v)
F['crash50'] = ((F.fwd12_loc <= -0.5) | (F.bankrupt12 == 1)).astype(float).where(v)
v3 = F.fwd36_eur.notna()
g3 = F[v3].groupby(['reg', 'date']).fwd36_eur
F.loc[v3, 'xs36_reg'] = F.fwd36_eur[v3] - g3.transform('mean')
F.loc[v3, 'rk36_reg'] = (g3.rank(method='average') - 0.5) / g3.transform('count')
F['x3'] = (F.fwd36_eur >= 2.0).astype(float).where(v3)
# ------------------------------------------------------------------ pulizia e salvataggio
F = F.replace([np.inf, -np.inf], nan)
RAW = ['px', 'sh', 'sh0', 'sh4', 'mcap', 'mcap_usd', 'ev', 'fx_px', 'fx_rep', 'rev_ttm', 'rev_ttm4', 'rev_ttm8', 'rev_q', 'rev_qp', 'revq_prev',
       'revg_ttm_prev', 'ni_ttm', 'ni_ttm4', 'ni_ttm8', 'ni_q', 'ni_qp', 'opi_ttm', 'opi_ttm4', 'ebitda_ttm', 'gp_ttm', 'gp_ttm4', 'rev_ttm4b',
       'rd_ttm', 'sga_ttm', 'fcf_ttm', 'cfo_ttm', 'capex_ttm', 'equity', 'debt', 'cash', 'ta', 'ta4', 'cur_a', 'cur_l', 'adv_usd',
       'gm4', 'opm4', 'n_prof_y', 'n_years', 'src', 'm0', 'cov', 'fin_end', 'fin_av', 'bal_end']
CTX = ['t', 'date', 'name', 'ex', 'country', 'region', 'reg', 'reg_rob', 'sector', 'sector_n', 'industry', 'excl_sector', 'cur_px', 'cur_rep',
       'per3', 'size', 'delisted', 'us_new', 'ext_fields', 'n_fail', 'GARP', 'core']
COLS = CTX + fv3.PREDICTORS + fv3.TARGETS + RAW
miss = [c for c in COLS if c not in F]; assert not miss, miss
F = F[COLS].copy()  # (deframmenta)
for c in F.columns:
    if F[c].dtype == 'float64' and c not in ('m0',): F[c] = F[c].astype('float32')
for c in ['name', 'ex', 'country', 'region', 'reg', 'reg_rob', 'sector', 'sector_n', 'industry', 'cur_px', 'cur_rep', 'per3', 'src']:
    F[c] = F[c].astype('category')
F = F.sort_values(['date', 't']).reset_index(drop=True)
F.to_pickle(f'{HERE}/features_v3.pkl')
print(F.shape, 'societa', F.t.nunique(), 'date', F.date.nunique(), 'MB', round(F.memory_usage(deep=True).sum() / 1e6))
