# 07/11: dal pannello grezzo (world_14) al pannello per i test (come world_05 + tune_common.load), con:
#  - FIX_PENCE ovunque: i prezzi in pence (GBX/GBp), ZAC, ILA si convertono con il cambio /100 (world_05 usava la sterlina);
#  - doppioni tolti: stessa societa' quotata due volte (classi A/C, ADR non riconosciuti, doppie quotazioni) riconosciuta
#    dall'impronta di bilancio (ricavi e utile 12 mesi in USD uguali alla stessa data); si tiene una sola riga per societa'
#    (borsa di casa > codice senza classe > codice piu' corto);
#  - liquidita' point-in-time con l'universo USA allargato (world_14b).
import pickle, sys, pandas as pd, numpy as np
from world_common import *
from tune_common import EXCL_S, PERIODS, period_of, FILTERS
from tune_01_panel import fwd
FIX_PENCE = True
TODAY = pd.Timestamp('2026-11-06')
F = pd.read_pickle(f'{BASE}/res/feat2_raw.pkl')
M = pd.read_pickle(f'{BASE}/res/meta2.pkl').drop_duplicates('t').set_index('t')
RQ = pd.read_pickle(f'{BASE}/res/rq2.pkl')
FX = pd.read_pickle(f'{BASE}/eod/fx.pkl').sort_index().ffill()
REB = sorted(F.date.unique()); NEXT = {t: (REB[i + 1] if i + 1 < len(REB) else TODAY) for i, t in enumerate(REB)}


def fx_at(c, t, pence_ok=False):
    if not pence_ok: c = {'GBX': 'GBP', 'GBp': 'GBP', 'ZAC': 'ZAR', 'ILA': 'ILS'}.get(c, c)
    elif c == 'GBp': c = 'GBX'
    if c not in FX.columns: return np.nan
    i = FX.index.searchsorted(t, side='right') - 1; return FX[c].iloc[max(i, 0)]


F['cur'] = F.cur.replace('', np.nan)
F = F.join(M[['ex', 'region', 'sector', 'industry', 'cur_px', 'delisted', 'name', 'country', 'new_fields']], on='t')
F['cur_rep'] = F.cur.where(F.cur.notna(), F.cur_px.replace({'GBX': 'GBP', 'GBp': 'GBP'}))
fxp, fxr = {}, {}
for (c, t), _ in F.groupby(['cur_px', 'date']): fxp[(c, t)] = fx_at(c, t, pence_ok=FIX_PENCE)
for (c, t), _ in F.groupby(['cur_rep', 'date']): fxr[(c, t)] = fx_at(c, t)
F['fx_px'] = [fxp.get((c, t), np.nan) for c, t in zip(F.cur_px, F.date)]
F['fx_rep'] = [fxr.get((c, t), np.nan) for c, t in zip(F.cur_rep, F.date)]
F['mcap_usd'] = F.sh * F.px * F.fx_px
F.loc[(F.mcap_usd > 6e12) | (F.mcap_usd < 1e6), 'mcap_usd'] = np.nan
F['mcap'] = F.mcap_usd / F.fx_rep
shr = F.sh0 / F.sh4; okS = shr.between(0.67, 1.5); adj = np.where(okS, F.sh4 / F.sh0, 1.0)
F['epsg'] = np.where(F.ni_ttm4 > 0, F.ni_ttm / F.ni_ttm4 * adj - 1, np.nan)
F['epsq'] = np.where(F.ni_qp > 0, F.ni_q / F.ni_qp * adj - 1, np.nan)
F['revq'] = np.where(F.rev_qp > 0, F.rev_q / F.rev_qp - 1, np.nan)
F['pe'] = F.mcap / F.ni_ttm; F['peg'] = F.pe / (F.epsg * 100)
F['roe'] = F.ni_ttm / F.equity; F['de'] = F.debt / F.equity; F['fcfy'] = F.fcf_ttm / F.mcap
F = F.replace([np.inf, -np.inf], np.nan)
F = F.join(RQ.drop_duplicates(['t', 'date']).set_index(['t', 'date']), on=['t', 'date'])
F = F[F.r.notna()]
cur_e = {}
for c in F.cur_px.dropna().unique():
    for t in REB:
        a = fx_at(c, t) / fx_at('EUR', t); b = fx_at(c, NEXT[t]) / fx_at('EUR', NEXT[t]); cur_e[(c, t)] = b / a - 1
F['r_eur'] = (1 + F.r) * (1 + np.array([cur_e.get((c, t), np.nan) for c, t in zip(F.cur_px, F.date)])) - 1
LQ = pd.read_pickle(f'{BASE}/res/liq_pit2.pkl').drop_duplicates(['t', 'date']).set_index(['t', 'date']).liq
F['liq'] = LQ.reindex(pd.MultiIndex.from_arrays([F.t, F.date])).fillna(False).values
homeok = pd.Series([(c in HOME[e]) if HOME[e] else True for c, e in zip(F.country, F.ex)], index=F.index)
base = (~F.name.fillna('').str.contains(r'\bCDR\b') & (homeok | F.country.isna()) & F.liq & (F.mcap_usd >= 300e6) & (F.rev_ttm > 0)).fillna(False)
F = F[base].copy()
# ------------------------------------------------------------------ doppioni
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
cnt = F.groupby('t').size()
DUP = []
def pref(t):
    c, e = t.rsplit('.', 1)
    return (e == 'US', '-' in c or '_' in c, len(c), c)
for (a, b), n in pairs.items():
    common = len(set(F.date[F.t == a]) & set(F.date[F.t == b]))
    if n >= max(3, 0.3 * common):
        lose = max(a, b, key=pref); keep = min(a, b, key=pref)
        DUP.append((keep, lose, n, common, M.name.get(keep), M.name.get(lose)))
D = pd.DataFrame(DUP, columns=['tiene', 'toglie', 'date_uguali', 'date_comuni', 'nome_tiene', 'nome_toglie'])
D.to_csv(f'{BASE}/res/doppioni.csv', index=False)
print('coppie doppie', len(D)); print(D.head(60).to_string())
# si toglie la riga doppia solo nelle date in cui esiste anche la quotazione tenuta (i cambi di codice restano coperti)
have = set(zip(F.t, F.date)); drop = set()
for keep, lose in zip(D.tiene, D.toglie):
    for d in F.date[F.t == lose]:
        if (keep, d) in have: drop.add((lose, d))
F = F[[(a, b) not in drop for a, b in zip(F.t, F.date)]].copy()
print('righe doppie tolte', len(drop))
# ------------------------------------------------------------------ come tune_common.load
F['excl_sector'] = F.sector.isin(EXCL_S)
F['per'] = F.date.map(period_of)
F['reg'] = F.region.replace({'Canada': 'Altri', 'Australia': 'Altri'})
C1 = set(pd.read_csv(f'{BASE}/res/candidates.csv').t)
F['us_new'] = (F.ex == 'US') & ~F.t.isin(C1)          # piccole/medie USA aggiunte il 07/11
F['size'] = pd.cut(F.mcap_usd, [0, 2e9, 10e9, 1e15], labels=['piccola', 'media', 'grande'])
F['revg_ttm'] = np.where(F.rev_ttm4 > 0, F.rev_ttm / F.rev_ttm4 - 1, np.nan)
F['revg_ttm_prev'] = np.where(F.rev_ttm8 > 0, F.rev_ttm4 / F.rev_ttm8 - 1, np.nan)
F['opm'] = F.opi_ttm / F.rev_ttm; F['opm4'] = F.opi_ttm4 / F.rev_ttm4; F['d_opm'] = F.opm - F.opm4
F['fcf_m'] = F.fcf_ttm / F.rev_ttm
shr = F.sh0 / F.sh4; F['dshares'] = np.where(shr.between(0.5, 2), shr - 1, np.nan)
F['logmcap'] = np.log10(F.mcap_usd)
# segnali nuovi
F['gm'] = (F.gp_ttm / F.rev_ttm).where(lambda s: s.between(-1, 0.999))
F['gm4'] = (F.gp_ttm4 / F.rev_ttm4b).where(lambda s: s.between(-1, 0.999))
F['d_gm'] = F.gm - F.gm4
F['rd_int'] = F.rd_ttm / F.rev_ttm
F['sga_int'] = F.sga_ttm / F.rev_ttm
F['cur_ratio'] = F.cur_a / F.cur_l
F = F.replace([np.inf, -np.inf], np.nan)
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
W = fwd(RQ.drop_duplicates(['t', 'date']))
F = F.merge(W, on=['t', 'date'], how='left')
g = F.groupby('date').f12; F['pct12'] = g.rank(pct=True)
F['W5'] = (F.pct12 >= 0.95) & F.f12.notna(); F['L20'] = (F.pct12 <= 0.20) & F.f12.notna()
F['L50'] = (F.f12 <= -0.5) & F.f12.notna(); F['MB3'] = (F.f36 >= 2.0) & F.f36.notna()
F.to_pickle(f'{BASE}/res/panel2.pkl')
print(F.shape, 'societa', F.t.nunique())
print(F[~F.excl_sector].groupby(['date']).size().iloc[[0, 16, 32, -1]])
print(F[~F.excl_sector].groupby('reg').t.nunique(), F[~F.excl_sector & (F.ex == 'US')].groupby('date').us_new.mean().iloc[[0, 30, -1]])
print('copertura campi nuovi (righe universo):', F[['gm', 'rd_int', 'surp_last', 'age_y', 'cur_ratio']].notna().mean().round(2).to_dict())
