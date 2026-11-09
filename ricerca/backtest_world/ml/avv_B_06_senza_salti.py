# Verifica avversariale prova B: prova 8, crolli e core GARP senza le righe con salti finti (flag da avv_B_05), e
# sensibilita' della stima 7.4 (mancanti nei quinti del blocco comune) alla regola di assegnazione.
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
ML = '${RICERCA_BASE}/backtest_world/ml'; BW = os.path.dirname(ML)
sys.path.insert(0, ML); sys.path.insert(0, BW)
from profili_common import profiles
import temi_common as tc
from tune_common import mask, BASE_P
from world_04_features import COVERED_OTHER
PB = f'{ML}/storico5/provaB'
F = pd.read_pickle(f'{PB}/matrice_B.pkl'); F['hist15'] = F.hist_y.clip(upper=15)
FL = pd.read_pickle(f'{ML}/avv_B_out/flag_salti_finti.pkl'); F = F.merge(FL, on=['t', 'date'], how='left', validate='1:1')
COMMON = {'dsh3': -1, 'hist15': +1, 'hi52': +1, 'n_beat4': +1}
L = {'QUAL': {**COMMON, 'vol1y': -1, 'roic': +1, 'opm_std5': -1, 'fcf_m': +1}, 'GARP': {**COMMON, 'vol1y': -1, 'roe': +1, 'fcf_m': +1, 'peg': -1},
     'CRESC': {**COMMON, 'opm_std5': -1, 'runway_y': +1, 'capex_int': -1}, 'PREPROF': {**COMMON, 'runway_y': +1, 'npm': +1}, 'TEMI': {**COMMON, 'fcf_m': +1}}
P, _ = profiles(F)
G = {'QUAL': P['QUAL'], 'GARP_c': P['GARP'] & (F.rev_cagr > 0.10), 'CRESC': P['CRESC'], 'PREPROF': P['PREPROF']}
V = pd.read_pickle(f'{PB}/temi_flags_B.pkl'); fl = V[V.B.fillna(False) | V.MOM.fillna(False)]; flagged = set(zip(fl.ind, fl.date))
G['TEMI_ex'] = pd.Series([k in flagged for k in zip(tc.norm_ind(F.industry), F.date)], index=F.index) & ~F.sector.astype(str).isin(['Financial Services', 'Real Estate', 'Financials'])
LST = {'QUAL': 'QUAL', 'GARP_c': 'GARP', 'CRESC': 'CRESC', 'PREPROF': 'PREPROF', 'TEMI_ex': 'TEMI'}
TEST = (F.anno >= 2006) & (F.anno <= 2011)


def myscore(X, lst):
    cols = []
    for c, s in lst.items():
        v = X[c].astype(float) * s; r = v.groupby(X.date).rank(method='average'); n = v.groupby(X.date).transform('count')
        cols.append(((r - 0.5) / n).fillna(0.5))
    return pd.concat(cols, axis=1).mean(axis=1)


def geo(r): r = np.asarray(r, float); return np.prod(1 + r) ** (4 / len(r)) - 1


out = []
for g, l in LST.items():
    X = F[G[g] & TEST].copy(); s = myscore(X, L[l])            # punteggio e quinti calcolati su tutti (come l'autore)
    q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
    for lab, keep3, keep12 in [('principale', np.ones(len(X), bool), np.ones(len(X), bool)), ('senza salti finti', ~X.bad3.values, ~X.bad12.values)]:
        Xr = X[keep3]; qr = q[keep3]
        U = Xr.groupby('date').f3.mean(); R1 = Xr[qr == 1].groupby('date').f3.mean().reindex(U.index).fillna(0); R5 = Xr[qr == 5].groupby('date').f3.mean().reindex(U.index).fillna(0)
        Xc = X[keep12]; qc = q[keep12]
        out.append(dict(profilo=g, versione=lab, Q1_vs_prof=geo(R1) - geo(U), Q5_vs_prof=geo(R5) - geo(U), cr_Q1=Xc.crash50[qc == 1].mean(),
                        cr_Q5=Xc.crash50[qc == 5].mean(), cr_prof=Xc.crash50.mean(), ecc_Q1_quota=Xc.top5_reg[qc == 1].sum() / max(Xc.top5_reg.sum(), 1)))
R = pd.DataFrame(out); print(R.round(3).to_string())
print(R.groupby('versione')[['Q1_vs_prof', 'Q5_vs_prof', 'cr_Q1', 'cr_Q5', 'cr_prof']].mean().round(4).to_string())
# core GARP senza le righe con f3 finto
CORE = mask(F, dict(BASE_P, revq=0.20)) & (F.hi52 >= 0.8).fillna(False) & (F.mcap_usd >= 2e9); UNI = ~F.excl_sector
DT = sorted(F.date[TEST].unique()); an = np.array([pd.Timestamp(d + pd.Timedelta(days=1)).year for d in DT])


def port(m, cost=0.005):
    d = F[m & TEST]; Gd = {t: x for t, x in d.groupby('date')}; r, n, prev = [], [], set()
    for t in DT:
        x = Gd.get(t); k = set(x.t) if x is not None else set(); g = x.f3.mean() if x is not None and len(x) else 0.0
        sold = len(prev - k) / len(prev) if prev else 0; bought = len(k - prev) / len(k) if k else 0
        r.append(g - cost * (sold + bought)); n.append(len(k)); prev = k
    return np.array(r), np.array(n)


for lab, ex in [('principale', pd.Series(False, index=F.index)), ('senza salti finti', F.bad3)]:
    rc, nc = port(CORE & ~ex); ru = F[UNI & TEST & ~ex].groupby('date').f3.mean().reindex(DT).values
    yr = {y: (round(float(np.prod(1 + rc[an == y]) - 1), 3), round(float(np.prod(1 + ru[an == y]) - 1), 3)) for y in (2008, 2009)}
    print(f'core GARP {lab}: {geo(rc):+.4f} contro {geo(ru):+.4f} -> {geo(rc) - geo(ru):+.4f} | 2008 e 2009 (core, universo): {yr}')
# ------------------------------------------------------------------ sensibilita' della stima 7.4
U = pd.read_pickle(f'{PB}/universo_A_copia.pkl'); M = pd.read_pickle(f'{PB}/meta.pkl').drop_duplicates('t').set_index('t')
A = U[(U.anno >= 2006) & (U.anno <= 2011)].copy(); A = A[~A.t.map(M.country).isin(COVERED_OTHER)]
Bm = F[TEST].copy(); Bm['s'] = myscore(Bm, COMMON); Bm['q'] = np.ceil(Bm.s.groupby(Bm.date).rank(pct=True) * 5).clip(1, 5)
inB = set(zip(Bm.t, Bm.date)); A['inB'] = [k in inB for k in zip(A.t, A.date)]
A['q_p52'] = np.ceil(A.p52.groupby(A.date).rank(pct=True) * 5).clip(1, 5); A['q_vol'] = np.ceil(A.vol.groupby(A.date).rank(pct=True) * 5).clip(1, 5)
Ak = A.set_index(['t', 'date']); ix = pd.MultiIndex.from_arrays([Bm.t, Bm.date])
Bm['q_p52'] = Ak.q_p52.reindex(ix).values; Bm['q_vol'] = Ak.q_vol.reindex(ix).values
x0 = A[~A.inB].copy(); ds = sorted(Bm.date.unique())


def est(bincols):
    Bm['bin'] = sum(Bm[c] * 10 ** i for i, c in enumerate(bincols)) if bincols else 0
    x = x0.copy(); x['bin'] = sum(x[c] * 10 ** i for i, c in enumerate(bincols)) if bincols else 0
    PQ = pd.crosstab([Bm.anno, Bm.bin], Bm.q, normalize='index'); PQ.columns = [int(c) for c in PQ.columns]
    x = x.join(PQ, on=['anno', 'bin'])
    for k in range(1, 6): x[k] = x[k].fillna(0.2)
    def qret(k):
        rb = Bm[Bm.q == k].groupby('date').f3.agg(['sum', 'count']).reindex(ds).fillna(0)
        w = x[k]; rx = (x.f3 * w).groupby(x.date).sum().reindex(ds).fillna(0); nx = w.groupby(x.date).sum().reindex(ds).fillna(0)
        return (rb['sum'] + rx) / (rb['count'] + nx)
    ru = A.groupby('date').f3.mean().reindex(ds)
    r1, r5 = qret(1), qret(5)
    return geo(r1) - geo(ru), geo(r5) - geo(ru), geo(r5) - geo(r1)


for lab, bc in [('autore: prezzo/massimo x volatilita', ['q_vol', 'q_p52']), ('solo prezzo/massimo', ['q_p52']), ('solo volatilita', ['q_vol']),
                ('a caso (stesse probabilita per tutte)', [])]:
    a, b, c = est(bc); print(f'stima 7.4, {lab:40s}: Q1 vs universo {a:+.4f}  Q5 vs universo {b:+.4f}  Q5-Q1 {c:+.4f}')
r1 = Bm[Bm.q == 1].groupby('date').f3.mean().reindex(ds); r5 = Bm[Bm.q == 5].groupby('date').f3.mean().reindex(ds)
print(f'sole sopravvissute: Q5-Q1 {geo(r5) - geo(r1):+.4f}')
