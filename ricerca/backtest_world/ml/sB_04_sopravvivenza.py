# Prova B, passo 4: quanto distorce l'archivio di sole societa' con bilanci (in pratica sopravvissute), 2006-2011.
# Confronto con l'universo di soli prezzi della prova A (storico5/universo_prezzi_us_v2.pkl, fotografia in provaB/), che
# contiene anche le societa' uscite dal listino. Misure:
#  1. per anno: quante righe dell'universo A mancano nella prova B e perche'; rendimento e crolli di A, di B e delle mancanti;
#  2. distorsione su una componente del punteggio misurabile per tutti (prezzo/massimo a 52 settimane) e sulla volatilita';
#  3. stima "se ci fossero": le mancanti messe nei quinti del blocco comune con le probabilita' osservate fra le sopravvissute
#     con lo stesso prezzo/massimo e la stessa volatilita' (ipotesi prudente: le mancanti hanno di solito bilanci peggiori).
import os, sys, warnings, numpy as np, pandas as pd
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML)
sys.path.insert(0, ML); sys.path.insert(0, BW)
from world_04_features import COVERED_OTHER
from profili_common import cagr_q
OUT = f'{ML}/storico5/provaB'
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
YEARS = list(range(2006, 2012))
U = pd.read_pickle(f'{OUT}/universo_A_copia.pkl')
A = U[(U.anno >= 2006) & (U.anno <= 2011)].copy()
B = pd.read_pickle(f'{OUT}/matrice_B.pkl'); B = B[(B.anno >= 2006) & (B.anno <= 2011)].copy()
M = pd.read_pickle(f'{OUT}/meta.pkl').drop_duplicates('t').set_index('t')
inB = set(zip(B.t, B.date))
A['inB'] = [k in inB for k in zip(A.t, A.date)]
A['scheda'] = A.t.isin(M.index)
A['adr'] = A.t.map(M.country).isin(COVERED_OTHER)
A['cat'] = np.select([A.inB, A.adr, A.uscita_pre2011 & ~A.scheda, A.uscita_pre2011, ~A.scheda],
                     ['B', 'ADR paese coperto', 'uscita prima di 06/2011, nessuna scheda', 'uscita prima di 06/2011, scheda vuota o inutilizzabile',
                      'viva a meta 2011, nessuna scheda'], 'scheda ma bilancio non utilizzabile, cap. vera <300 M$, ricavi nulli o doppione')
A = A[~A.adr].copy()          # gli ADR di paesi coperti sono fuori anche dal 2012-2026: tolti da entrambi i lati
A['crollo'] = A.f12 <= -0.5
print('categorie (righe 2006-11, ADR esclusi):'); print(A.cat.value_counts().to_string())
print('per anno, quota di righe:'); print(pd.crosstab(A.anno, A.cat, normalize='index').round(3).to_string())
comp = lambda z: float(np.prod(1 + z.fillna(0).values) - 1)
R = []
for y in YEARS + ['2006-11']:
    a = A if y == '2006-11' else A[A.anno == y]
    b, x = a[a.inB], a[~a.inB]
    ds = sorted(a.date.unique())
    ra = a.groupby('date').f3.mean().reindex(ds); rb = b.groupby('date').f3.mean().reindex(ds); rx = x.groupby('date').f3.mean().reindex(ds)
    f = (lambda z: cagr_q(z)) if y == '2006-11' else comp
    R.append(dict(anno=y, titoli_A=len(a) / len(ds), titoli_B=len(b) / len(ds), quota_mancanti=len(x) / len(a),
                  quota_mancanti_uscite=float(x.uscita_pre2011.sum() / len(a)),
                  rend_A=f(ra), rend_B=f(rb), rend_mancanti=f(rx), premio_sopravv=f(rb) - f(ra),
                  f12_medio_A=a.groupby('date').f12.mean().mean(), f12_medio_B=b.groupby('date').f12.mean().mean(), f12_medio_mancanti=x.groupby('date').f12.mean().mean(),
                  crolli_A=a.crollo.mean(), crolli_B=b.crollo.mean(), crolli_mancanti=x.crollo.mean(),
                  quota_crolli_nascosti=float(x.crollo.sum() / max(a.crollo.sum(), 1)),
                  quota_disastri_nascosti=float(x.L20.sum() / max(a.L20.sum(), 1)), quota_eccezionali_nascosti=float(x.W5.sum() / max(a.W5.sum(), 1))))
RT = pd.DataFrame(R); RT.to_csv(f'{OUT}/sopravvivenza_B.csv', index=False); print(RT.round(3).to_string())
# ------------------------------------------------------------------ 2. distorsione su prezzo/massimo e volatilita'
def bands(X, col, hi_good=True):
    q = np.ceil(X[col].groupby(X.date).rank(pct=True) * 5).clip(1, 5)
    worst = q == (1 if hi_good else 5); best = q == (5 if hi_good else 1)
    ds = sorted(X.date.unique())
    rw = X[worst].groupby('date').f3.mean().reindex(ds); rb = X[best].groupby('date').f3.mean().reindex(ds); ru = X.groupby('date').f3.mean().reindex(ds)
    return dict(crolli_peggiore=X.crollo[worst].mean(), crolli_migliore=X.crollo[best].mean(), crolli_tutti=X.crollo.mean(),
                rapporto_peggiore_media=X.crollo[worst].mean() / X.crollo.mean(),
                peggiore_vs_univ=cagr_q(rw) - cagr_q(ru), migliore_vs_univ=cagr_q(rb) - cagr_q(ru), migliore_meno_peggiore=cagr_q(rb) - cagr_q(rw))


D2 = []
for per, yy in [('2006-07', [2006, 2007]), ('2008-09', [2008, 2009]), ('2010-11', [2010, 2011]), ('2006-11', YEARS)]:
    a = A[A.anno.isin(yy)]
    for lab, X in [('A: tutte (prova A)', a), ('B: solo con bilanci', a[a.inB])]:
        for col, hg, nm in [('p52', True, 'prezzo/massimo 52 sett.'), ('vol', False, 'volatilita 1 anno')]:
            D2.append(dict(periodo=per, universo=lab, variabile=nm, **bands(X, col, hg)))
        g = X.p52 >= 0.40
        D2.append(dict(periodo=per, universo=lab, variabile='guardia: sotto il 40% del massimo', crolli_peggiore=X.crollo[~g].mean(),
                       crolli_migliore=X.crollo[g].mean(), crolli_tutti=X.crollo.mean(), rapporto_peggiore_media=X.crollo[~g].mean() / X.crollo.mean()))
DT2 = pd.DataFrame(D2); DT2.to_csv(f'{OUT}/sopravvivenza_componenti_B.csv', index=False); print(DT2.round(3).to_string())
# dove cadrebbero le mancanti: quinti di prezzo/massimo e di volatilita' calcolati su tutto l'universo A
A['q_p52'] = np.ceil(A.p52.groupby(A.date).rank(pct=True) * 5).clip(1, 5)
A['q_vol'] = np.ceil(A.vol.groupby(A.date).rank(pct=True) * 5).clip(1, 5)
x = A[~A.inB]
print('mancanti per quinto di prezzo/massimo (1 = piu lontane dal massimo):', x.q_p52.value_counts(normalize=True).sort_index().round(3).to_dict())
print('mancanti per quinto di volatilita (5 = piu volatili):', x.q_vol.value_counts(normalize=True).sort_index().round(3).to_dict())
print('uscite pre-2011 fra le mancanti per quinto di prezzo/massimo:', x[x.uscita_pre2011].q_p52.value_counts(normalize=True).sort_index().round(3).to_dict())
# ------------------------------------------------------------------ 3. stima "se ci fossero": blocco comune
SRC = open(f'{ML}/sint_01_coerenza.py').read(); NS = {}
exec(SRC[SRC.index('COMMON = {'):SRC.index('# cancelli')], {}, NS)
GLOB = {'np': np, 'pd': pd}
exec('def score' + SRC.split('def score')[1].split('def quint_stats')[0], GLOB)
Bm = B.copy(); Bm['hist15'] = Bm.hist_y.clip(upper=15)
Bm['s'] = GLOB['score'](Bm, NS['COMMON'])
Bm['q'] = np.ceil(Bm.s.groupby(Bm.date).rank(pct=True) * 5).clip(1, 5)
Ak = A.set_index(['t', 'date'])
Bm['bin'] = (Ak.q_p52.reindex(pd.MultiIndex.from_arrays([Bm.t, Bm.date])).values * 10 +
             Ak.q_vol.reindex(pd.MultiIndex.from_arrays([Bm.t, Bm.date])).values)
x = A[~A.inB].copy(); x['bin'] = x.q_p52 * 10 + x.q_vol
PQ = pd.crosstab([Bm.anno, Bm.bin], Bm.q, normalize='index')          # P(quinto | anno, fascia prezzo x volatilita') fra le sopravvissute
PQ.columns = [int(c) for c in PQ.columns]
x = x.join(PQ, on=['anno', 'bin'])
for k in range(1, 6): x[k] = x[k].fillna(0.2)
S = []
for per, yy in [('2006-07', [2006, 2007]), ('2008-09', [2008, 2009]), ('2010-11', [2010, 2011]), ('2006-11', YEARS)]:
    b = Bm[Bm.anno.isin(yy)]; xx = x[x.anno.isin(yy)]; ds = sorted(b.date.unique())
    def qret(k, with_x):
        rb = b[b.q == k].groupby('date').r_eur.agg(['sum', 'count']).reindex(ds).fillna(0)
        if with_x:
            w = xx[k]; rx = (xx.f3 * w).groupby(xx.date).sum().reindex(ds).fillna(0); nx = w.groupby(xx.date).sum().reindex(ds).fillna(0)
            return (rb['sum'] + rx) / (rb['count'] + nx), float(nx.sum() / (rb['count'].sum() + nx.sum()))
        return rb['sum'] / rb['count'], 0.0
    def ucr(with_x):
        cr = b.groupby('date').crash50.sum() if with_x is False else None
    out = {}
    for wx in (False, True):
        ru_b = b.groupby('date').r_eur.mean().reindex(ds)
        ru = A[A.anno.isin(yy)].groupby('date').f3.mean().reindex(ds) if wx else ru_b
        r1, s1 = qret(1, wx); r5, s5 = qret(5, wx)
        tag = 'con le mancanti (stima)' if wx else 'solo sopravvissute'
        c1 = b.crash50[b.q == 1].sum() + (xx[1] * xx.crollo).sum() if wx else b.crash50[b.q == 1].sum()
        n1 = (b.q == 1).sum() + (xx[1].sum() if wx else 0)
        c5 = b.crash50[b.q == 5].sum() + (xx[5] * xx.crollo).sum() if wx else b.crash50[b.q == 5].sum()
        n5 = (b.q == 5).sum() + (xx[5].sum() if wx else 0)
        S.append(dict(periodo=per, versione=tag, Q1_vs_univ=cagr_q(r1) - cagr_q(ru), Q5_vs_univ=cagr_q(r5) - cagr_q(ru), Q5_meno_Q1=cagr_q(r5) - cagr_q(r1),
                      crolli_Q1=c1 / n1, crolli_Q5=c5 / n5, quota_mancanti_in_Q1=s1, quota_mancanti_in_Q5=s5, rend_univ=cagr_q(ru)))
ST = pd.DataFrame(S); ST.to_csv(f'{OUT}/sopravvivenza_stima_blocco_comune.csv', index=False); print(ST.round(3).to_string())
