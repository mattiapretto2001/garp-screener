# Verifica avversariale della prova B (08/11/2026). Ricalcolo INDIPENDENTE (codice mio, non le funzioni dell'autore) di:
#  1. prova 8: quinto basso vs profilo (composto) nei 5 profili, piu' la differenza ARITMETICA e il suo t;
#  2. crolli medi quinto basso / alto / profilo;
#  3. premio delle sopravvissute (B 5,4% contro A 2,9%);
#  4. core GARP contro l'universo GARP (-3,9).
# Poi i controlli di robustezza: senza il 2009, senza il 2008, rendimenti trimestrali tagliati all'1%-99%, senza i titoli con
# salti di prezzo sospetti, solo righe dell'universo "scambi prudenti" della prova A, sensibilita' della stima 7.4.
# Nessuna chiamata EODHD. Scrive solo in ml/avv_B_out/.
import os, sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML)
sys.path.insert(0, ML); sys.path.insert(0, BW)
from profili_common import profiles
import temi_common as tc
from tune_common import mask, BASE_P
OUT = f'{ML}/avv_B_out'; os.makedirs(OUT, exist_ok=True)
PB = f'{ML}/storico5/provaB'
F = pd.read_pickle(f'{PB}/matrice_B.pkl')
F['hist15'] = F.hist_y.clip(upper=15)
COMMON = {'dsh3': -1, 'hist15': +1, 'hi52': +1, 'n_beat4': +1}
L = {'QUAL': {**COMMON, 'vol1y': -1, 'roic': +1, 'opm_std5': -1, 'fcf_m': +1},
     'GARP': {**COMMON, 'vol1y': -1, 'roe': +1, 'fcf_m': +1, 'peg': -1},
     'CRESC': {**COMMON, 'opm_std5': -1, 'runway_y': +1, 'capex_int': -1},
     'PREPROF': {**COMMON, 'runway_y': +1, 'npm': +1},
     'TEMI': {**COMMON, 'fcf_m': +1}}
P, _ = profiles(F)
G = {'QUAL': P['QUAL'], 'GARP_c': P['GARP'] & (F.rev_cagr > 0.10), 'CRESC': P['CRESC'], 'PREPROF': P['PREPROF']}
V = pd.read_pickle(f'{PB}/temi_flags_B.pkl')
fl = V[V.B.fillna(False) | V.MOM.fillna(False)]; flagged = set(zip(fl.ind, fl.date))
G['TEMI_ex'] = pd.Series([k in flagged for k in zip(tc.norm_ind(F.industry), F.date)], index=F.index) & \
    ~F.sector.astype(str).isin(['Financial Services', 'Real Estate', 'Financials'])
LST = {'QUAL': 'QUAL', 'GARP_c': 'GARP', 'CRESC': 'CRESC', 'PREPROF': 'PREPROF', 'TEMI_ex': 'TEMI'}
TEST = (F.anno >= 2006) & (F.anno <= 2011)


def myscore(X, lst):
    cols = []
    for c, s in lst.items():
        v = X[c].astype(float) * s
        r = v.groupby(X.date).rank(method='average'); n = v.groupby(X.date).transform('count')
        cols.append(((r - 0.5) / n).fillna(0.5))
    return pd.concat(cols, axis=1).mean(axis=1)


def geo(r): r = np.asarray(r, float); return np.prod(1 + r) ** (4 / len(r)) - 1


def q1_stats(X, s, col='r'):
    q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
    U = X.groupby('date')[col].mean(); R1 = X[q == 1].groupby('date')[col].mean().reindex(U.index).fillna(0)
    R5 = X[q == 5].groupby('date')[col].mean().reindex(U.index).fillna(0)
    d = R1 - U
    ok = X.fwd12.notna()
    return dict(Q1_geo=geo(R1) - geo(U), Q1_arit_ann=4 * d.mean(), t_Q1=d.mean() / d.std(ddof=1) * np.sqrt(len(d)),
                Q5_geo=geo(R5) - geo(U), vol_Q1=R1.std() * 2, vol_prof=U.std() * 2,
                cr_Q1=X.crash50[ok & (q == 1)].mean(), cr_Q5=X.crash50[ok & (q == 5)].mean(), cr_prof=X.crash50[ok].mean())


def run_profiles(mask_rows, col='r', tag=''):
    out = []
    for g, l in LST.items():
        X = F[G[g] & TEST & mask_rows].copy(); s = myscore(X, L[l])
        out.append(dict(variante=tag, profilo=g, n_data=int(X.groupby('date').size().median()), **q1_stats(X, s, col)))
    return pd.DataFrame(out)


F['r'] = F.f3.astype(float)
# rendimenti tagliati all'1%-99% per data (robustezza ai pochi nomi estremi)
lo = F.groupby('date').r.transform(lambda z: z.quantile(0.01)); hi = F.groupby('date').r.transform(lambda z: z.quantile(0.99))
F['r_w'] = F.r.clip(lo, hi)
# titoli con salti di prezzo trovati a mano (f3 > +100% incoerente con la storia nota del titolo, o crollo finto subito dopo)
SUS = ['GSS', 'CBB', 'NXGN', 'RRD', 'UFS', 'LFC', 'TRQ']
allr = pd.Series(True, index=F.index)
RES = [run_profiles(allr, 'r', 'principale (ricalcolo)'),
       run_profiles(F.anno != 2009, 'r', 'senza il 2009'),
       run_profiles(F.anno != 2008, 'r', 'senza il 2008'),
       run_profiles(~F.anno.isin([2008, 2009]), 'r', 'senza 2008 e 2009'),
       run_profiles(allr, 'r_w', 'rendimenti tagliati 1-99%'),
       run_profiles(~F.t.isin(SUS), 'r', 'senza 7 titoli con salti sospetti')]
# universo A con scambi prudenti (come sA_03_test.py): tengo solo le righe B che ci sono anche li'
try:
    from sA_common import build
    Pn = pd.read_pickle(f'{ML}/storico5/pannello_prezzi_us_v2.pkl'); Pn = Pn[Pn.date <= '2011-09-30'].reset_index(drop=True)
    C = pd.read_pickle(f'{ML}/storico5/volumi_corretti_A.pkl').set_index(['t', 'date'])
    j = C.reindex(pd.MultiIndex.from_frame(Pn[['t', 'date']])); has = j.dv_raw.notna().values
    Pp = Pn.copy(); Pp.loc[has, 'dv63'] = np.minimum(Pn.dv63.values[has], j.dv_raw.values[has])
    Pp.loc[has, 'px'] = np.minimum(Pn.px.values[has], j.px_p.values[has])
    U2p = build(Pp); kp = set(zip(U2p.t, U2p.date))
    inp = pd.Series([k in kp for k in zip(F.t, F.date)], index=F.index)
    print('righe B 2006-11 nell universo prudente:', round(float(inp[TEST].mean()), 4), int((~inp & TEST).sum()), 'tolte', flush=True)
    RES.append(run_profiles(inp, 'r', 'solo universo scambi prudenti'))
    U2p.to_pickle(f'{OUT}/universo_A_prudente.pkl')
except Exception as e:
    print('prudente non calcolato:', repr(e))
RT = pd.concat(RES); RT.to_csv(f'{OUT}/prova8_robustezza.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(RT.round(3).to_string())
summ = RT.groupby('variante', sort=False).agg(Q1_sotto=('Q1_geo', lambda s: int((s < 0).sum())), Q1_geo_med=('Q1_geo', 'mean'),
                                              Q1_arit_sotto=('Q1_arit_ann', lambda s: int((s < 0).sum())), Q1_arit_med=('Q1_arit_ann', 'mean'),
                                              t_min=('t_Q1', 'min'), t_max=('t_Q1', 'max'), cr_Q1=('cr_Q1', 'mean'), cr_Q5=('cr_Q5', 'mean'), cr_prof=('cr_prof', 'mean'))
print(summ.round(3).to_string()); summ.to_csv(f'{OUT}/prova8_sintesi.csv')
# ------------------------------------------------------------------ 3. premio delle sopravvissute
U = pd.read_pickle(f'{PB}/universo_A_copia.pkl'); M = pd.read_pickle(f'{PB}/meta.pkl').drop_duplicates('t').set_index('t')
from world_04_features import COVERED_OTHER
A = U[(U.anno >= 2006) & (U.anno <= 2011)].copy(); A = A[~A.t.map(M.country).isin(COVERED_OTHER)]
Bt = F[TEST]
ga = geo(A.groupby('date').f3.mean().values); gb = geo(Bt.groupby('date').f3.mean().values)
print(f'\nsopravvissute: A {ga:.4f}  B {gb:.4f}  premio {gb - ga:+.4f} | crolli A {(A.f12 <= -0.5).mean():.4f} B {Bt.crash50.mean():.4f}')
try:
    Ap = U2p[(U2p.anno >= 2006) & (U2p.anno <= 2011)]; Ap = Ap[~Ap.t.map(M.country).isin(COVERED_OTHER)]
    gap = geo(Ap.groupby('date').f3.mean().values)
    print(f'  universo A prudente: {gap:.4f} (premio B {gb - gap:+.4f}), crolli {(Ap.f12 <= -0.5).mean():.4f}, righe per data {len(Ap) / Ap.date.nunique():.0f}')
except Exception as e:
    print(e)
# quanto vivono le societa' B dopo il 2011
lastB = pd.to_datetime(Bt.drop_duplicates('t')['last'])
print('societa B quotate ancora al 2017:', round(float((lastB >= '2017-01-01').mean()), 4), '| al 2026:', round(float((lastB >= '2026-01-01').mean()), 4),
      '| uscite 2012-2016:', int(((lastB >= '2011-10-01') & (lastB < '2017-01-01')).sum()))
# ------------------------------------------------------------------ 4. core GARP (codice dell'autore per le maschere, portafoglio mio)
CORE = mask(F, dict(BASE_P, revq=0.20)) & (F.hi52 >= 0.8).fillna(False) & (F.mcap_usd >= 2e9)
UNI = ~F.excl_sector
DT = sorted(F.date[TEST].unique())


def port(m, col='r', cost=0.005):
    d = F[m & TEST]; Gd = {t: x for t, x in d.groupby('date')}; r, n, prev = [], [], set()
    for t in DT:
        x = Gd.get(t); k = set(x.t) if x is not None else set()
        g = x[col].mean() if x is not None and len(x) else 0.0
        sold = len(prev - k) / len(prev) if prev else 0; bought = len(k - prev) / len(k) if k else 0
        r.append(g - cost * (sold + bought)); n.append(len(k)); prev = k
    return np.array(r), np.array(n)


rc, nc = port(CORE); ru = F[UNI & TEST].groupby('date').r.mean().reindex(DT).values
print(f'\ncore GARP: {geo(rc):.4f}  universo GARP {geo(ru):.4f}  diff {geo(rc) - geo(ru):+.4f}  titoli medi {nc.mean():.1f}  min {nc.min()}')
# quanto conta il 2008: diff senza i 4 trimestri del 2008
an = np.array([pd.Timestamp(d + pd.Timedelta(days=1)).year for d in DT])
for y in (2008, 2009):
    k = an != y
    print(f'  core senza il {y}: {geo(rc[k]) - geo(ru[k]):+.4f}')
# contributo dei singoli titoli: togli il peggior titolo per contributo
d = F[CORE & TEST].copy(); d['w'] = 1 / d.groupby('date').t.transform('count'); d['contr'] = d.w * d.r
print('  peggiori contributi (somma pesata dei rendimenti trimestrali):'); print(d.groupby(['t', 'name']).contr.sum().nsmallest(6).round(3).to_string())
print('  migliori:'); print(d.groupby(['t', 'name']).contr.sum().nlargest(4).round(3).to_string())
# portafogli a caso: stesso numero di titoli per data, presi dall'universo GARP >=2 Mld$ (posizione del core nella distribuzione)
rng = np.random.default_rng(7); U2 = F[UNI & TEST & (F.mcap_usd >= 2e9)]; R2 = {t: x.r.values for t, x in U2.groupby('date')}
sims = []
for it in range(2000):
    rr = [rng.choice(R2[t], min(n, len(R2[t])), replace=False).mean() if n > 0 else 0.0 for t, n in zip(DT, nc)]
    sims.append(geo(rr) - geo(ru))
sims = np.array(sims)
print(f'  portafogli a caso (lordi) con lo stesso numero di titoli: mediana {np.median(sims):+.4f}, 5-95% {np.quantile(sims, .05):+.4f} / {np.quantile(sims, .95):+.4f}; '
      f'quota peggiore del core (netto) {float((sims < geo(rc) - geo(ru)).mean()):.3f}')
