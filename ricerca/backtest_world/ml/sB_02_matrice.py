# Prova B, passo 2: dalla tabella point-in-time (sB_01) alla matrice delle variabili, con le STESSE formule del 2012-2026:
# world_15_prep (cambi, capitalizzazione, EPS, PEG, ROE, filtri GARP, doppioni per impronta di bilancio) e fv3_02_build
# (tutte le variabili di features_v3, aggregati di industria). Universo: righe dell'universo della prova A (prezzo >=3 $,
# scambi >=3 M$, 200 giorni di prezzi, capitalizzazione >=300 M$ dove nota) che hanno un bilancio utilizzabile alla data,
# capitalizzazione vera >=300 M$ e ricavi >0 (come la base del 2012-2026). ADR di paesi coperti esclusi come nel 2012-2026.
# Esito: rendimento a 12 mesi (e a 3 mesi) della prova A, in dollari, con la regola di uscita (ultimo prezzo <25% del massimo
# dell'anno = -100%). Nessuna chiamata EODHD.
import os, sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML)
sys.path.insert(0, BW); sys.path.insert(0, ML)
from world_04_features import COVERED_OTHER
from tune_common import EXCL_S, FILTERS
import fv3
OUT = f'{ML}/storico5/provaB'
nan = np.nan
R = pd.read_pickle(f'{OUT}/bilanci_pit_raw.pkl')
M = pd.read_pickle(f'{OUT}/meta.pkl').drop_duplicates('t').set_index('t')
U = pd.read_pickle(f'{OUT}/universo_A_copia.pkl')
FX = pd.read_pickle(f'{BW}/eod/fx.pkl').sort_index().ffill()
UC = ['t', 'date', 'dv63', 'n1y', 'f12', 'f12_end', 'f3', 'f3_end', 'p52', 'vol', 'mom12', 'src', 'last', 'name', 'uscita_pre2011',
      'cap', 'cap_vera', 'fuori_borsa', 'codice_old', 'anno']
F = R.merge(U[UC], on=['t', 'date'], how='inner', validate='1:1')
F = F.join(M[['name_f', 'sector', 'industry', 'country', 'ext_fields', 'cur_px']], on='t')
log = {'righe_pit_nell_universo_A': len(F)}


def fx_at(c, t):
    c = {'GBX': 'GBP', 'GBp': 'GBP', 'ZAC': 'ZAR', 'ILA': 'ILS'}.get(c, c)
    if c == 'USD': return 1.0
    if c not in FX.columns: return nan
    i = FX.index.searchsorted(t, side='right') - 1; return FX[c].iloc[max(i, 0)]


# ------------------------------------------------------------------ come world_15_prep
F['cur'] = F.cur.replace('', nan)
F['cur_rep'] = F.cur.where(F.cur.notna(), 'USD')
fxr = {(c, t): fx_at(c, t) for (c, t), _ in F.groupby(['cur_rep', 'date'])}
F['fx_px'] = 1.0
F['fx_rep'] = [fxr.get((c, t), nan) for c, t in zip(F.cur_rep, F.date)]
F['mcap_usd'] = F.sh * F.px * F.fx_px
F.loc[(F.mcap_usd > 6e12) | (F.mcap_usd < 1e6), 'mcap_usd'] = nan
F['mcap'] = F.mcap_usd / F.fx_rep
shr = F.sh0 / F.sh4; okS = shr.between(0.67, 1.5); adj = np.where(okS, F.sh4 / F.sh0, 1.0)
F['epsg'] = np.where(F.ni_ttm4 > 0, F.ni_ttm / F.ni_ttm4 * adj - 1, nan)
F['epsq'] = np.where(F.ni_qp > 0, F.ni_q / F.ni_qp * adj - 1, nan)
F['revq'] = np.where(F.rev_qp > 0, F.rev_q / F.rev_qp - 1, nan)
F['pe'] = F.mcap / F.ni_ttm; F['peg'] = F.pe / (F.epsg * 100)
F['roe'] = F.ni_ttm / F.equity; F['de'] = F.debt / F.equity; F['fcfy'] = F.fcf_ttm / F.mcap
F = F.replace([np.inf, -np.inf], nan)
adr = F.country.isin(COVERED_OTHER)
log['adr_paesi_coperti_tolte'] = int(adr.sum())
PLUS = os.environ.get('PLUS') == '1'      # variante: tiene anche le righe senza numero di azioni (capitalizzazione ignota), come la prova A
capok = (F.mcap_usd >= 300e6) | (F.mcap_usd.isna() & F.sh.isna()) if PLUS else (F.mcap_usd >= 300e6)
base = (~F.name.fillna('').str.contains(r'\bCDR\b') & ~adr & capok & (F.rev_ttm > 0)).fillna(False)
log['tolte_cap_vera_sotto_300M_o_ricavi_nulli'] = int((~base & ~adr).sum())
F = F[base].copy()
# doppioni per impronta di bilancio (stesso codice di world_15_prep)
F['rev_usd'] = F.rev_ttm * F.fx_rep; F['ni_usd'] = F.ni_ttm * F.fx_rep
pairs = {}
for t, x in F[F.rev_usd > 0].groupby('date'):
    x = x.sort_values('rev_usd'); rv = x.rev_usd.values; ni = x.ni_usd.values; tk = x.t.values
    for i in range(len(x)):
        j = i + 1
        while j < len(x) and rv[j] <= rv[i] * 1.01:
            if abs(ni[j] - ni[i]) <= 0.02 * max(abs(ni[i]), abs(ni[j]), 1e6) and tk[i] != tk[j]:
                k = tuple(sorted((tk[i], tk[j]))); pairs[k] = pairs.get(k, 0) + 1
            j += 1
pref = lambda c: ('-' in c or '_' in c, len(c), c)
DUP = []
for (a, b), n in pairs.items():
    common = len(set(F.date[F.t == a]) & set(F.date[F.t == b]))
    if n >= max(3, 0.3 * common):
        DUP.append((min(a, b, key=pref), max(a, b, key=pref), n, common))
have = set(zip(F.t, F.date)); drop = set()
for keep, lose, _, _ in DUP:
    for d in F.date[F.t == lose]:
        if (keep, d) in have: drop.add((lose, d))
F = F[[(a, b) not in drop for a, b in zip(F.t, F.date)]].copy()
pd.DataFrame(DUP, columns=['tiene', 'toglie', 'date_uguali', 'date_comuni']).to_csv(f'{OUT}/doppioni_B.csv', index=False)
log['doppioni_tolti'] = len(drop)
F['excl_sector'] = F.sector.isin(EXCL_S)
F['reg'] = 'USA'; F['region'] = 'USA'
F['revg_ttm'] = np.where(F.rev_ttm4 > 0, F.rev_ttm / F.rev_ttm4 - 1, nan)
F['revg_ttm_prev'] = np.where(F.rev_ttm8 > 0, F.rev_ttm4 / F.rev_ttm8 - 1, nan)
F['opm'] = F.opi_ttm / F.rev_ttm; F['opm4'] = F.opi_ttm4 / F.rev_ttm4; F['d_opm'] = F.opm - F.opm4
F['fcf_m'] = F.fcf_ttm / F.rev_ttm
shr = F.sh0 / F.sh4; F['dshares'] = np.where(shr.between(0.5, 2), shr - 1, nan)
F['gm'] = (F.gp_ttm / F.rev_ttm).where(lambda s: s.between(-1, 0.999))
F['gm4'] = (F.gp_ttm4 / F.rev_ttm4b).where(lambda s: s.between(-1, 0.999))
F['d_gm'] = F.gm - F.gm4
F['cur_ratio'] = F.cur_a / F.cur_l
F = F.replace([np.inf, -np.inf], nan)
F['ok_settore'] = ~F.excl_sector
F['ok_ROE'] = ((F.ni_ttm > 0) & (F.equity > 0) & (F.roe > 0.15)).fillna(False)
F['ok_D/E'] = ((F.equity > 0) & (F.de < 1)).fillna(False)
F['ok_FCF'] = (F.fcf_ttm > 0).fillna(False)
F['ok_ricavi_q'] = (F.revq > 0.05).fillna(False)
F['ok_EPS_q'] = (F.epsq > 0.05).fillna(False)
F['ok_PEG'] = ((F.ni_ttm > 0) & (F.epsg > 0) & (F.peg > 0) & (F.peg < 2)).fillna(False)
F['ok_CAGR'] = (F.rev_cagr > 0.10).fillna(False)
F['n_fail'] = (~F[[f'ok_{f}' for f in FILTERS]]).sum(axis=1)
F['GARP'] = F.n_fail == 0
# ------------------------------------------------------------------ come fv3_02_build
REB = sorted(F.date.unique()); IDX = {d: i for i, d in enumerate(REB)}
for c in ['cash', 'debt', 'cur_a', 'cur_l', 'capex_ttm']: F.loc[F[c] < 0, c] = nan
for c in ['ta', 'ta4']: F.loc[F[c] <= 0, c] = nan


def safe_div(a, b, pos_den=True):
    a, b = a.astype(float), b.astype(float)
    ok = (b > 0) if pos_den else (b != 0)
    return (a / b).where(ok)


cash0, debt0 = F.cash.fillna(0.0), F.debt.fillna(0.0)
F['ev'] = F.mcap + debt0 - cash0
F['pe'] = safe_div(F.mcap, F.ni_ttm)
F['ey'] = safe_div(F.ni_ttm, F.mcap)
peg = F.pe / (F.epsg * 100)
F['peg'] = peg.where((F.pe > 0) & (F.epsg > 0) & (peg >= 0.05))
F['ev_ebitda'] = (F.ev / F.ebitda_ttm).where((F.ebitda_ttm > 0) & (F.ev > 0))
F['ebit_ev'] = safe_div(F.opi_ttm, F.ev)
F['ev_sales'] = (F.ev / F.rev_ttm).where((F.ev > 0) & (F.rev_ttm > 0))
F['fcfy'] = safe_div(F.fcf_ttm, F.mcap)
F['pb'] = safe_div(F.mcap, F.equity)
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
F['revg_ttm'] = safe_div(F.rev_ttm, F.rev_ttm4) - 1
F['revg_ttm_prev'] = safe_div(F.rev_ttm4, F.rev_ttm8) - 1
F['accel_q'] = F.revq - F.revq_prev
F['accel_y'] = F.revg_ttm - F.revg_ttm_prev
F['oplev'] = (safe_div(F.opi_ttm, F.opi_ttm4) - 1) - F.revg_ttm
F['d_opm'] = F.opm - F.opm4
F['d_gm'] = F.gm - F.gm4
F['turn_profit'] = ((F.ni_ttm > 0) & (F.ni_ttm4 <= 0)).astype(float).where(F.ni_ttm.notna() & F.ni_ttm4.notna())
F['rd_int'] = safe_div(F.rd_ttm, F.rev_ttm)
F['sga_int'] = safe_div(F.sga_ttm, F.rev_ttm)
F['capex_int'] = safe_div(F.capex_ttm, F.rev_ttm)
F['asset_g'] = safe_div(F.ta, F.ta4) - 1
F['burner'] = (F.fcf_ttm < 0).astype(float).where(F.fcf_ttm.notna())
burn = (-F.fcf_ttm).clip(lower=0)
F['cash_mcap'] = safe_div(F.cash, F.mcap)
F['burn_mcap'] = safe_div(burn, F.mcap)
F['runway_y'] = (F.cash / burn).where(burn > 0).clip(upper=10)
F.loc[(F.fcf_ttm >= 0) & F.cash.notna(), 'runway_y'] = 10.0
F['cash_debt'] = (F.cash / F.debt).where(F.debt > 0).clip(upper=10)
F.loc[(F.debt <= 0) & F.cash.notna(), 'cash_debt'] = 10.0
F['netcash_mcap'] = safe_div(cash0 - debt0, F.mcap).where(F.cash.notna() | F.debt.notna())
F['adv_usd'] = F.adv_loc * F.fx_px
F['log_adv'] = np.log10(F.adv_usd.where(F.adv_usd > 0))
F['turnover'] = safe_div(F.adv_usd, F.mcap_usd)
F['logmcap'] = np.log10(F.mcap_usd)
F['fin_age_d'] = (F.date - pd.to_datetime(F.fin_end)).dt.days.astype(float)
SECN = {'Financials': 'Financial Services', 'Financial': 'Financial Services', 'Information Technology': 'Technology', 'Materials': 'Basic Materials',
        'Consumer Discretionary': 'Consumer Cyclical', 'Health Care': 'Healthcare', 'Consumer Staples': 'Consumer Defensive',
        'Consumer Non-Cyclicals': 'Consumer Defensive', 'Electric Utilities': 'Utilities', 'Multi-Utilities': 'Utilities',
        'Equity Real Estate Investment Trusts (REITs)': 'Real Estate', 'Regional Banks': 'Financial Services', 'Capital Markets': 'Financial Services',
        'Diversified Financial Services': 'Financial Services', 'IT Services': 'Technology', 'Consumer Goods': 'Consumer Defensive',
        'Industrial Goods': 'Industrials', 'Road & Rail': 'Industrials', 'Internet & Direct Marketing Retail': 'Consumer Cyclical',
        'Services': 'Industrials', 'Academic & Educational Services': 'Consumer Defensive'}
F['sector_n'] = F.sector.replace(SECN)
F['core'] = F.GARP & (F.revq > 0.20).fillna(False) & (F.hi52 >= 0.8).fillna(False) & (F.mcap_usd >= 2e9)
# industria (qui solo USA: nel 2012-2026 tutte le regioni insieme)
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
# ------------------------------------------------------------------ esiti (dalla prova A, in dollari)
F['fwd12'] = F.f12.astype(float)
v = F.fwd12.notna()
g0 = F[v].groupby('date').fwd12
F.loc[v, 'rk12_reg'] = (g0.rank(method='average') - 0.5) / g0.transform('count')
F['rk12'] = F.rk12_reg
F['top5_reg'] = (F.rk12_reg >= 0.95).astype(float).where(v)
F['bot20_reg'] = (F.rk12_reg <= 0.20).astype(float).where(v)
F['crash50'] = (F.fwd12 <= -0.5).astype(float).where(v)
F['r_eur'] = F.f3.astype(float)          # NB: rendimento del trimestre in dollari (nome tenuto per usare le funzioni congelate)
F = F.replace([np.inf, -np.inf], nan)
miss = [c for c in fv3.PREDICTORS if c not in F]
assert not miss, miss
F = F.sort_values(['date', 't']).reset_index(drop=True)
F.to_pickle(f'{OUT}/matrice_Bplus.pkl' if PLUS else f'{OUT}/matrice_B.pkl')
log['righe_finali'] = len(F); log['titoli'] = F.t.nunique()
print(log)
print('righe per data (anno):', (F.groupby('anno').size() / F.groupby('anno').date.nunique()).round(0).to_dict())
print('copertura (2006-11):', F[F.anno >= 2006][['dsh3', 'hist_y', 'hi52', 'n_beat4', 'n_est4', 'vol1y', 'roic', 'roe', 'opm_std5', 'fcf_m', 'peg',
                                                'runway_y', 'capex_int', 'npm', 'gm', 'cur_ratio', 'ma200', 'rev_cagr']].notna().mean().round(3).to_dict())
