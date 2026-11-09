# Prova B, passo 3: UNA lettura dei punteggi congelati sugli USA 2006-2011 (societa' con bilanci EODHD = in pratica sopravvissute).
# Definizioni lette TALI E QUALI da sint_01_coerenza.py (COMMON, L, GUARD, funzioni score e quint_stats) e da profili_common
# (cancelli), temi_01/temi_02 (regola dei temi), scr_common (core GARP, Crescita/Moonshot). Nessun ritocco.
# Unica differenza obbligata: l'esito e' in dollari (solo USA), quindi la colonna r_eur contiene il rendimento del trimestre in $.
# Periodi: una data appartiene all'anno in cui parte la finestra (31/12/2007 conta nel 2008). Test: date 31/12/2005 - 30/09/2011.
import os, sys, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML)
sys.path.insert(0, ML); sys.path.insert(0, BW)
import fv3
from profili_common import profiles, ic_series, nwt, cagr_q
import temi_common as tc
from tune_common import mask, BASE_P
OUT = f'{ML}/storico5/provaB'
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 80); pd.set_option('display.max_rows', 400)
MAT = os.environ.get('MATB', 'matrice_B'); SFX = '' if MAT == 'matrice_B' else '_' + MAT
F = pd.read_pickle(f'{OUT}/{MAT}.pkl')
F['hist15'] = F.hist_y.clip(upper=15)
# ------------------------------------------------------------------ definizioni congelate, lette dal file del 07/11
SRC = open(f'{ML}/sint_01_coerenza.py').read()
NS = {}
exec(SRC[SRC.index('COMMON = {'):SRC.index('# cancelli')], {}, NS)
COMMON, L = NS['COMMON'], NS['L']
GLOB = {'np': np, 'pd': pd, 'cagr_q': cagr_q, 'COST': 0.005}
exec('def score' + SRC.split('def score')[1].split('def quint_stats')[0], GLOB)
exec('def quint_stats' + SRC.split('def quint_stats')[1].split('\n\nrows = []')[0], GLOB)
score, quint_stats = GLOB['score'], GLOB['quint_stats']
gexpr = [l for l in SRC.splitlines() if l.startswith('GUARD = ')][0].split('=', 1)[1].split('#')[0].strip()
GUARD = eval(gexpr, {'F': F})
print('liste congelate:', json.dumps(L)); print('guardia:', gexpr)
P, ind = profiles(F)
G = dict(P)
G['GARP_c'] = P['GARP'] & (F.rev_cagr > 0.10)
# ------------------------------------------------------------------ temi: regola fissata (temi_01 + temi_02), solo societa' USA
T = F[['t', 'date', 'industry', 'sector_n', 'mcap_usd', 'fx_rep', 'rev_ttm', 'rev_ttm4', 'rev_ttm8', 'rev_ttm4b', 'rev_q', 'rev_qp',
       'gp_ttm', 'gp_ttm4', 'opi_ttm', 'opi_ttm4', 'accel_y', 'd_gm', 'mom12_1', 'mom6', 'ma200']].copy()
T['ind'] = tc.norm_ind(T.industry)
T = T[T.ind.notna() & (T.ind != 'Other')].copy()
DD = sorted(F.date.unique()); IX = {d: i for i, d in enumerate(DD)}
T['di'] = T.date.map(IX)
sec = T.groupby('ind').sector_n.agg(lambda s: s.mode().iloc[0])
fx = T.fx_rep.astype(float)
T['ru'], T['ru4'], T['ru8'] = T.rev_ttm * fx, T.rev_ttm4 * fx, T.rev_ttm8 * fx
T['rq'], T['rqp'] = T.rev_q * fx, T.rev_qp * fx
T['gpu'], T['gpu4'], T['ru4b'] = T.gp_ttm * fx, T.gp_ttm4 * fx, T.rev_ttm4b * fx
T['opu'], T['opu4'] = T.opi_ttm * fx, T.opi_ttm4 * fx
T['us'] = True


def agg(g):
    o = {'n': len(g)}
    m = (g.ru4 > 0) & g.ru.notna(); o['g_agg'] = g.ru[m].sum() / g.ru4[m].sum() - 1 if m.sum() >= 3 else np.nan
    m2 = m & (g.ru8 > 0)
    o['accel_agg'] = (g.ru[m2].sum() / g.ru4[m2].sum() - g.ru4[m2].sum() / g.ru8[m2].sum()) if m2.sum() >= 3 else np.nan
    mq = (g.rqp > 0) & g.rq.notna(); o['gq_agg'] = g.rq[mq].sum() / g.rqp[mq].sum() - 1 if mq.sum() >= 3 else np.nan
    mm = g.mom12_1.notna(); o['pos'] = (g.mom12_1[mm] > 0).mean() if mm.sum() >= 3 else np.nan
    o['mom_med'] = g.mom12_1.median()
    for tag, sub in (('', g), ('_us', g[g.us])):
        mg = (sub.ru > 0) & (sub.ru4b > 0) & sub.gpu.notna() & sub.gpu4.notna()
        o['d_gm_agg' + tag] = (sub.gpu[mg].sum() / sub.ru[mg].sum() - sub.gpu4[mg].sum() / sub.ru4b[mg].sum()) if mg.sum() >= 3 else np.nan
        o['n_gm' + tag] = int(mg.sum())
    mo = (g.ru > 0) & (g.ru4 > 0) & g.opu.notna() & g.opu4.notna()
    o['d_opm_agg'] = (g.opu[mo].sum() / g.ru[mo].sum() - g.opu4[mo].sum() / g.ru4[mo].sum()) if mo.sum() >= 3 else np.nan
    return pd.Series(o)


IP = T.groupby(['ind', 'date']).apply(agg).reset_index()
IP['sector'] = IP.ind.map(sec); IP['eligible'] = ~IP.sector.isin(tc.EXCL_SECT); IP['di'] = IP.date.map(IX)
lag = IP[['ind', 'di', 'pos']].copy(); lag['di'] = lag.di + 2
IP = IP.merge(lag, on=['ind', 'di'], how='left', suffixes=('', '_l2'))
IP['d_pos2'] = IP.pos - IP.pos_l2
IP['qa'] = IP.gq_agg - IP.g_agg
IP['d_marg'] = IP.d_gm_agg_us.where(IP.n_gm_us >= 3, IP.d_gm_agg.where(IP.n_gm >= 5, IP.d_opm_agg))
IP['valid'] = IP.n >= tc.MIN_N
V = IP[IP.valid & IP.eligible].copy()
COMP = ['accel_agg', 'qa', 'd_pos2', 'pos', 'd_marg']
for c in COMP: V['rk_' + c] = V.groupby('date')[c].rank(pct=True)
V['scoreB'] = V[['rk_' + c for c in COMP]].mean(axis=1, skipna=True)
top = lambda s: s.groupby(V.date).rank(pct=True, ascending=True) > 0.9
V['B'] = top(V.scoreB); V['MOM'] = top(V.mom_med)
V.to_pickle(f'{OUT}/temi_flags_B{SFX}.pkl')
fl = V[V.B.fillna(False) | V.MOM.fillna(False)]
flagged = set(zip(fl.ind, fl.date))
key = list(zip(tc.norm_ind(F.industry), F.date))
G['TEMI_ex'] = pd.Series([k in flagged for k in key], index=F.index) & ~F.sector.astype(str).isin(['Financial Services', 'Real Estate', 'Financials'])
# ------------------------------------------------------------------ periodo di prova
TEST = (F.anno >= 2006) & (F.anno <= 2011)
YEARS = list(range(2006, 2012))
LIST_OF = {'QUAL': 'QUAL', 'GARP_c': 'GARP', 'CRESC': 'CRESC', 'PREPROF': 'PREPROF', 'TEMI_ex': 'TEMI', 'GARP': 'GARP', 'TEMI': 'TEMI'}
MAIN = ['QUAL', 'GARP_c', 'CRESC', 'PREPROF', 'TEMI_ex']
TECH = ['fin_age_d', 'n_est4', 'logmcap', 'log_adv', 'ind_n']
ALL73 = [c for c in fv3.PREDICTORS if c not in TECH and fv3.DIRECTION.get(c, 0) != 0]
assert len(ALL73) == 73
UNIV_Q = F[TEST].groupby('date').r_eur.mean()       # universo delle sopravvissute (tutte le societa' con bilanci), a pesi uguali


def score_miss(X, lst, fill):
    Z = {}
    for c, s in lst.items():
        v = X[c].astype(float) * s
        g = v.groupby(X.date)
        Z[c] = ((g.rank(method='average') - 0.5) / g.transform('count')).fillna(fill)
    return pd.DataFrame(Z).mean(axis=1)


def yearly(X, s):
    """per anno: IC, rendimento composto dei 4 trimestri (quinto basso, alto, profilo, universo sopravvissute), crolli"""
    q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
    ic = ic_series(s, X.rk12_reg, X.date)
    out = []
    for y in YEARS:
        m = (X.anno == y).values
        if not m.any(): continue
        ds = sorted(X.date[m].unique())
        r = lambda mm: X[mm & m].groupby('date').r_eur.mean().reindex(ds)
        comp = lambda z: float(np.prod(1 + z.fillna(0).values) - 1)
        ok = X.fwd12.notna().values & m
        out.append(dict(anno=y, n=int(np.median(X[m].groupby('date').size())), IC=ic.reindex(ds).mean(),
                        Q1=comp(r(q.values == 1)), Q5=comp(r(q.values == 5)), profilo=comp(r(np.ones(len(X), bool))),
                        sopravv=comp(UNIV_Q.reindex(ds)),
                        crolli_Q1=X.crash50[ok & (q.values == 1)].mean(), crolli_Q5=X.crash50[ok & (q.values == 5)].mean(),
                        crolli_prof=X.crash50[ok].mean()))
    return pd.DataFrame(out)


def full(X, s, cost=0.005):
    GLOB['COST'] = cost
    r = quint_stats(X, s)
    GLOB['COST'] = 0.005
    ic = ic_series(s, X.rk12_reg, X.date)
    q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
    ok = X.fwd12.notna()
    d10 = s.groupby(X.date).rank(pct=True) > 0.9
    R5 = X[q == 5].groupby('date').r_eur.mean(); R1 = X[q == 1].groupby('date').r_eur.mean(); Up = X.groupby('date').r_eur.mean()
    Us = UNIV_Q.reindex(Up.index)
    an = pd.Series([pd.Timestamp(d + pd.Timedelta(days=1)).year for d in ic.index], index=ic.index)
    d1 = (R1.reindex(Up.index).fillna(0) - Up)
    r.update(IC=ic.mean(), t_IC=nwt(ic), IC_pos_anni=int(sum(ic[an == y].mean() > 0 for y in YEARS)),
             t_Q1=d1.mean() / d1.std() * np.sqrt(len(d1)),
             Q5_sopravv=cagr_q(R5) - cagr_q(Us), Q1_sopravv=cagr_q(R1) - cagr_q(Us), prof_sopravv=cagr_q(Up) - cagr_q(Us),
             cagr_Q1=cagr_q(R1), cagr_Q5=cagr_q(R5), cagr_prof=cagr_q(Up), cagr_sopravv=cagr_q(Us),
             crolli_Q1=X.crash50[ok & (q == 1)].mean(), crolli_Q5=X.crash50[ok & (q == 5)].mean(), crolli_D10=X.crash50[ok & d10].mean(),
             crolli_prof=X.crash50[ok].mean(), dis_Q1=X.bot20_reg[ok & (q == 1)].mean(), dis_Q5=X.bot20_reg[ok & (q == 5)].mean(),
             dis_prof=X.bot20_reg[ok].mean(), ecc_D10=X.top5_reg[ok & d10].mean(), ecc_prof=X.top5_reg[ok].mean())
    return r


ROWS, YR, REF = [], [], []
for gname, lname in LIST_OF.items():
    m = G[gname] & TEST
    X = F[m].copy(); s = score(X, L[lname])
    r = dict(cancello=gname, lista=lname, n_var=len(L[lname]), soc_per_data=int(X.groupby('date').size().median()), **full(X, s))
    r['Q5_U_netto_1pc'] = full(X, s, 0.01)['Q5_U_netto']
    gx = GUARD[X.index]; ok = X.fwd12.notna()
    r.update(guardia_esclusi=1 - gx.mean(), crolli_esclusi=X.crash50[~gx & ok].mean(), crolli_ammessi=X.crash50[gx & ok].mean(),
             ecc_esclusi=X.top5_reg[~gx & ok].mean(), ecc_ammessi=X.top5_reg[gx & ok].mean())
    # dati mancanti = 25 (variante dichiarata, prova 13) e stime battute mancanti se non ci sono stime (controllo)
    s25 = score_miss(X, L[lname], 0.25); r['IC_mancanti25'] = ic_series(s25, X.rk12_reg, X.date).mean()
    r['Q1_U_mancanti25'] = quint_stats(X, s25)['Q1_U']
    X2 = X.copy(); X2.loc[X2.n_est4.fillna(0) == 0, 'n_beat4'] = np.nan; s2 = score(X2, L[lname])
    r['IC_stime_solo_se_ci_sono'] = ic_series(s2, X.rk12_reg, X.date).mean(); r['Q1_U_stime_solo_se_ci_sono'] = quint_stats(X2, s2)['Q1_U']
    # nessuna variabile mancante: quota di righe con >=2 mancanti
    r['quota_2_mancanti'] = float((X[list(L[lname])].isna().sum(axis=1) >= 2).mean())
    ROWS.append(r)
    y = yearly(X, s); y.insert(0, 'cancello', gname); YR.append(y)
    # riferimenti (prova 8): diluizione da sola, sola bassa volatilita', media delle 73 variabili con segno a priori
    for nm, lst in [('diluizione da sola', {'dsh3': -1}), ('sola bassa volatilita', {'vol1y': -1}),
                    ('73 variabili, segno a priori', {c: int(fv3.DIRECTION[c]) for c in ALL73}), ('solo blocco comune', COMMON)]:
        sr = score(X, lst); q5 = quint_stats(X, sr); icr = ic_series(sr, X.rk12_reg, X.date)
        REF.append(dict(cancello=gname, riferimento=nm, IC=icr.mean(), t_IC=nwt(icr), Q1_U=q5['Q1_U'], Q5_U=q5['Q5_U'], Q5_U_netto=q5['Q5_U_netto']))
    print(gname, 'fatto', flush=True)
RT = pd.DataFrame(ROWS); YT = pd.concat(YR); RF = pd.DataFrame(REF)
RT.to_csv(f'{OUT}/punteggi_B{SFX}.csv', index=False); YT.to_csv(f'{OUT}/punteggi_B_per_anno{SFX}.csv', index=False); RF.to_csv(f'{OUT}/riferimenti_B{SFX}.csv', index=False)
print(RT.round(3).T.to_string()); print(YT.round(3).to_string()); print(RF.round(3).to_string())
# ------------------------------------------------------------------ variabili singole (prove 3-7) sull'universo delle sopravvissute
X = F[TEST].copy()
SV = []


def ic_var(X, c, sign, sub=None, lab=None):
    Z = X if sub is None else X[sub]
    v = Z[c].astype(float) * sign
    ok = v.notna()
    ic = ic_series(v[ok], Z.rk12_reg[ok], Z.date[ok])
    q = np.ceil(v[ok].groupby(Z.date[ok]).rank(pct=True) * 5).clip(1, 5)
    Zo = Z[ok]; U = Zo.groupby('date').r_eur.mean()
    R1 = Zo[q == 1].groupby('date').r_eur.mean().reindex(U.index); R5 = Zo[q == 5].groupby('date').r_eur.mean().reindex(U.index)
    ok12 = Zo.fwd12.notna()
    icy = {y: ic[Zo.drop_duplicates('date').set_index('date').anno.reindex(ic.index) == y].mean() for y in YEARS}
    return dict(variabile=lab or c, segno_atteso=sign, copertura=float(ok.mean()), IC=ic.mean(), t_IC=nwt(ic), anni_IC_pos=int(sum(v > 0 for v in icy.values())),
                Q_peggiore_U=cagr_q(R1) - cagr_q(U), Q_migliore_U=cagr_q(R5) - cagr_q(U),
                crolli_peggiore=Zo.crash50[ok12 & (q == 1)].mean(), crolli_migliore=Zo.crash50[ok12 & (q == 5)].mean(),
                crolli_tutti=Zo.crash50[ok12].mean(), **{f'IC_{y}': icy[y] for y in YEARS})


for c, sgn in COMMON.items(): SV.append(ic_var(X, c, sgn))
SV.append(ic_var(X, 'vol1y', -1))
SV.append(ic_var(X, 'roic', +1, X.ni_ttm > 0, 'roic (solo in utile)'))
SV.append(ic_var(X, 'roe', +1, X.ni_ttm > 0, 'roe (solo in utile)'))
SV.append(ic_var(X, 'n_beat4', +1, X.n_est4.fillna(0) > 0, 'n_beat4 (solo con stime)'))
SV.append(ic_var(X, 'dsh1', -1))
SVT = pd.DataFrame(SV); SVT.to_csv(f'{OUT}/variabili_B{SFX}.csv', index=False); print(SVT.round(3).to_string())
# storia sotto gli 8 anni (penalita'), stime: chi le ha e' un gruppo di sopravvissute?
ok = X.fwd12.notna()
h8 = X.hist_y < 8
print('storia <8 anni: quota', round(h8.mean(), 3), 'crolli', round(X.crash50[ok & h8].mean(), 3), 'contro', round(X.crash50[ok & ~h8].mean(), 3),
      '| rango medio', round(X.rk12_reg[h8].mean(), 3), round(X.rk12_reg[~h8].mean(), 3))
he = X.n_est4.fillna(0) > 0
print('con stime: quota', round(he.mean(), 3), 'crolli', round(X.crash50[ok & he].mean(), 3), 'senza', round(X.crash50[ok & ~he].mean(), 3),
      '| rendimento 12m medio', round(X.fwd12[he].mean(), 3), round(X.fwd12[~he].mean(), 3))
# crescita a campana (prova 7): decili di crescita dei ricavi 12 mesi
dec = np.ceil(X.revg_ttm.groupby(X.date).rank(pct=True) * 10).clip(1, 10)
cb = X.groupby(dec).agg(rango_medio=('rk12_reg', 'mean'), crolli=('crash50', 'mean'), n=('t', 'size'))
print('crescita ricavi per decile:'); print(cb.round(3).to_string()); cb.to_csv(f'{OUT}/campana_B{SFX}.csv')
# guardia (prova 2) sull'universo intero delle sopravvissute
gx = GUARD[X.index]
print('guardia universo: esclusi', round(1 - gx.mean(), 3), 'crolli esclusi/ammessi', round(X.crash50[~gx & ok].mean(), 3), round(X.crash50[gx & ok].mean(), 3),
      '| per anno:', {y: (round(X.crash50[~gx & ok & (X.anno == y)].mean(), 3), round(X.crash50[gx & ok & (X.anno == y)].mean(), 3)) for y in YEARS})
# ------------------------------------------------------------------ core GARP e Crescita (Moonshot): portafogli trimestrali contro l'universo GARP
UNI = ~F.excl_sector
mc = F.mcap_usd
CORE = mask(F, dict(BASE_P, revq=0.20)) & (F.hi52 >= 0.8).fillna(False) & (mc >= 2e9)       # peg <0,05 gia' mancante (guardia PEG)
GLIST = mask(F, BASE_P)
fcf, cash, debt = F.fcf_ttm, F.cash, F.debt
runway = (fcf >= 0) | fcf.isna() | ((cash / fcf.abs()) > 2)
debt_ok = (debt <= 0) | debt.isna() | ((cash > 0) & (debt / cash <= 2)) | ((F.opi_ttm > 0) & ((debt - cash.fillna(0)) / F.opi_ttm <= 2.5))
liq_ok = F.cur_ratio.isna() | (F.cur_ratio > 1.2) | (cash >= debt)
dil_ok = F.dshares.isna() | (F.dshares < 0.15)
MB = (UNI & (F.rev_usd > 100e6) & (F.revq > 0.25) & (F.gm > 0.25) & (F.ma200 > 1) & runway & debt_ok & liq_ok & dil_ok).fillna(False)
MOON = MB & mc.between(3e8, 15e9) & (F.hi52 >= 0.70).fillna(False)
CR = MB & (F.hi52 >= 0.70).fillna(False)
COST = 0.005
DT = sorted(F.date[TEST].unique())


def run(m):
    d = F[m & TEST]; Gd = {t: x for t, x in d.groupby('date')}; r, n, prev = {}, {}, set()
    for t in DT:
        x = Gd.get(t); k = set(x.t) if x is not None else set()
        g = x.r_eur.mean() if x is not None and len(x) else 0.0
        sold = len(prev - k) / len(prev) if prev else 0; bought = len(k - prev) / len(k) if k else 0
        r[t] = g - COST * (sold + bought); n[t] = len(k); prev = k
    return pd.Series(r), pd.Series(n)


uni_r = F[UNI & TEST].groupby('date').r_eur.mean().reindex(DT)
uni2_r = F[UNI & TEST & (mc >= 2e9)].groupby('date').r_eur.mean().reindex(DT)
anno_of = F[TEST].drop_duplicates('date').set_index('date').anno
SCR = []
for nm, m, ref, refn in [('Core GARP (>=2 Mld$)', CORE, uni_r, 'universo GARP'), ('Core GARP (>=2 Mld$)', CORE, uni2_r, 'universo GARP >=2 Mld$'),
                         ('GARP di oggi (lista intera)', GLIST, uni_r, 'universo GARP'),
                         ('Crescita, regole Moonshot, tutte le taglie', CR, uni_r, 'universo GARP'),
                         ('Crescita, regole Moonshot, >=2 Mld$', CR & (mc >= 2e9), uni2_r, 'universo GARP >=2 Mld$'),
                         ('Moonshot 0,3-15 Mld$', MOON, F[UNI & TEST & mc.between(3e8, 15e9)].groupby('date').r_eur.mean().reindex(DT), 'universo GARP 0,3-15 Mld$')]:
    r, n = run(m); d = r - ref
    ok = (m & TEST & F.fwd12.notna())
    row = dict(lista=nm, confronto=refn, titoli_medi=n.mean(), date_vuote=int((n == 0).sum()), cagr=cagr_q(r), cagr_rif=cagr_q(ref), diff=cagr_q(r) - cagr_q(ref),
               t=d.mean() / d.std() * np.sqrt(len(d)), t_nw=nwt(d, 2), crolli=F.crash50[ok].mean(), crolli_rif=F.crash50[UNI & TEST & F.fwd12.notna()].mean(),
               disastri=F.bot20_reg[ok].mean())
    for y in YEARS:
        ds = [t for t in DT if anno_of[t] == y]
        row[f'r_{y}'] = float(np.prod(1 + r[ds].values) - 1); row[f'rif_{y}'] = float(np.prod(1 + ref[ds].values) - 1); row[f'n_{y}'] = n[ds].mean()
    SCR.append(row)
ST = pd.DataFrame(SCR); ST.to_csv(f'{OUT}/screener_B{SFX}.csv', index=False); print(ST.round(3).T.to_string())
# ------------------------------------------------------------------ profili: quanti, sovrapposizioni, copertura
print('societa per data nei profili (mediana):', {g: int(F[G[g] & TEST].groupby('date').size().median()) for g in LIST_OF})
print('industrie temi valide per data:', V.groupby('date').size().median(), 'segnalate B|MOM per data:', fl.groupby('date').size().median())
print(fl[(fl.date.dt.month == 12)][['date', 'ind', 'B', 'MOM']].sort_values('date').to_string())
