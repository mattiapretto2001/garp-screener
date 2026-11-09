# F2 passo 4: i segnali insider trovano piu' vincitori? Universo USA di soli prezzi (storico5/universo_prezzi_us_v2, uscite incluse,
# date 31/12/2005 - 30/09/2024), esiti dal giorno di fine trimestre (il segnale e' gia' depositato a quella data).
# Esiti: W5 = 5% migliore a 12 mesi nell'universo alla data; X3 = valore x3 a 36 mesi (+200%); L50 = -50% o peggio a 12 mesi
# (fallimento = -100%); ecc = rendimento a 12 mesi meno la media dell'universo alla data.
# 2000-2011: f12 corretto come in avv_A_19 (crolli finti, guadagni finti, fallimenti). f36 = 12 trimestri f3 concatenati (uscita =
# si resta in contanti); "X3 prudente" = senza trimestri con +150% o piu' (salti sospetti).
# Periodi per anno di partenza (data + 1 giorno): 2006-11, 2012-17, 2018-24. Taglie: piccole 0,3-2, medie 2-15, grandi >15 Mld$.
# t "non sovrapposti": differenza segnale - universo per data, una data per anno (4 serie, una per trimestre di partenza:
# media e minimo dei 4 t); per X3 una data ogni 3 anni (12 serie, media dei t). Caso: nomi estratti a caso dalla stessa data
# e taglia, 1.000 estrazioni.
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML); OUT = f'{ML}/f2'
AV = os.path.join(os.path.dirname(BW), 'avvA')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 400)
SIG = ['ANY', 'C2_30', 'C2_90', 'C3_90', 'BIG1M', 'PCT20', 'CEO100']
rng = np.random.default_rng(11)
# ------------------------------------------------------------------ universo ed esiti
U = pd.read_pickle(f'{ML}/storico5/universo_prezzi_us_v2.pkl')
U = U[(U.date >= '2005-12-31')].copy()
S = pd.read_pickle(f'{AV}/salti_class2.pkl'); S = S[S.innesto | S.split_api.notna() | (S.vol_giorno < 2)]
G = pd.read_pickle(f'{AV}/guadagni.pkl'); G = G[(G.salto >= 0.8) & ((G.vol_giorno < 2) | G.split_api.notna() | (G.zero_prima >= 0.5))]
Fb = pd.read_pickle(f'{AV}/fallimenti.pkl'); Fb = Fb[Fb.f12_ultimo > -0.5]
k = pd.MultiIndex.from_frame(U[['t', 'date']])
a = S.set_index(['t', 'date']).f12_tronco.reindex(k).values; b = G.set_index(['t', 'date']).f12_senza.reindex(k).values
c = Fb.set_index(['t', 'date']).f12_ultimo.reindex(k).values
fix = np.where(~np.isnan(a), a, np.where(~np.isnan(c), c, np.where(~np.isnan(b), b, np.nan)))
U['f12c'] = np.clip(np.where(U.storico & ~np.isnan(fix), fix, U.f12), -1, 10)
print('righe f12 corrette (solo 2000-11):', int((U.storico & ~np.isnan(fix)).sum()))
P = pd.read_pickle(f'{ML}/storico5/pannello_prezzi_us_v2.pkl')[['t', 'date', 'f3', 'f3_end']].sort_values(['t', 'date'])
P['g'] = 1 + P.f3; P['end'] = P.f3_end.fillna(False)
f36, big = {}, {}
for t, g in P.groupby('t'):
    d = g.date.values; gv = g.g.values; ev = g.end.values; n = len(g)
    for i in range(n):
        acc, ok, j, jump = 1.0, False, i, False
        for q in range(12):
            if j >= n: break
            exp = pd.Timestamp(d[i]) + pd.offsets.QuarterEnd(q) if q else pd.Timestamp(d[i])
            if pd.Timestamp(d[j]) != exp or np.isnan(gv[j]): break
            acc *= gv[j]; jump |= gv[j] >= 2.5
            if ev[j]: ok = True; break
            if q == 11: ok = True
            j += 1
        if ok: f36[(t, d[i])] = acc - 1; big[(t, d[i])] = jump
U['f36'] = [f36.get((t, np.datetime64(d)), np.nan) for t, d in zip(U.t, U.date)]
U['jump'] = [big.get((t, np.datetime64(d)), False) for t, d in zip(U.t, U.date)]
U['ok12'] = U.f12c.notna(); U['ok36'] = U.f36.notna() & (U.date <= '2022-12-31')   # dopo: 36 mesi non ancora completi per i vivi
U['W5'] = (U.groupby('date').f12c.rank(pct=True) >= 0.95) & U.ok12
U['L50'] = (U.f12c <= -0.5) & U.ok12
U['X3'] = (U.f36 >= 2.0) & U.ok36
U['X3p'] = U.X3 & ~U.jump
U['ecc'] = U.f12c - U.groupby('date').f12c.transform('mean')
U['anno'] = (U.date + pd.Timedelta(days=1)).dt.year
U['per'] = pd.cut(U.anno, [2005, 2011, 2017, 2026], labels=['2006-11', '2012-17', '2018-24'])
U['taglia'] = pd.cut(U.cap_use, [0, 2e9, 15e9, 1e15], labels=['piccole 0,3-2', 'medie 2-15', 'grandi >15'])
# CONTROLLO AGGIUNTO DOPO LA PRIMA LETTURA (a posteriori, non e' una variante del segnale): caso anche a parita' di volatilita'
# (quintile per data) e di distanza dal massimo a 52 settimane (quintile per data), perche' gli insider comprano dopo i cali.
U['vq'] = U.groupby('date').vol.transform(lambda v: pd.qcut(v.rank(method='first'), 5, labels=False)).fillna(-1)
U['pq'] = U.groupby('date').p52.transform(lambda v: pd.qcut(v.rank(method='first'), 5, labels=False)).fillna(-1)
SG = pd.read_pickle(f'{OUT}/segnali_trim.pkl')
U = U.merge(SG, on=['t', 'date'], how='left')
for s in SIG: U[s] = U[s].fillna(False).astype(bool)
L = pd.read_pickle(f'{OUT}/link_cik_codice.pkl')
U['linked'] = U.t.isin(L.t)
print('righe universo', len(U), '| righe di codici con almeno un acquisto di dirigenti collegato:', round(U.linked.mean(), 3), '| per periodo',
      U.groupby('per').linked.mean().round(3).to_dict(), '| per taglia', U.groupby('taglia').linked.mean().round(3).to_dict())
print('X3 disponibili fino a', U[U.ok36].date.max().date(), '| f12 fino a', U[U.ok12].date.max().date())
U[['t', 'date', 'per', 'taglia', 'cap_use', 'vol', 'p52', 'vq', 'pq', 'f12c', 'f36', 'W5', 'L50', 'X3', 'X3p', 'ecc', 'linked'] + SIG + ['n_ins90', 'val90']].to_pickle(f'{OUT}/pannello_f2.pkl')


def tnon(D, sig, tgt, okc, step):
    """t su date non sovrapposte: differenza (tasso segnale - tasso universo) per data"""
    x = D[D[okc]]
    n = x.groupby('date')[sig].sum()
    rs = x[x[sig]].groupby('date')[tgt].mean(); ra = x.groupby('date')[tgt].mean()
    dif = (rs - ra.reindex(rs.index))
    dif = dif[(n.reindex(dif.index) >= 5).values].dropna()
    if len(dif) < 4: return np.nan, np.nan
    dd = sorted(x.date.unique()); idx = {d: i for i, d in enumerate(dd)}
    ts = []
    for off in range(step):
        v = dif[[idx[d] % step == off for d in dif.index]]
        if len(v) >= 3 and v.std() > 0: ts.append(v.mean() / v.std() * np.sqrt(len(v)))
    return (np.mean(ts), np.min(np.abs(ts)) * np.sign(np.mean(ts))) if ts else (np.nan, np.nan)


def caso(D, sig, tgt, okc, reps=1000, by=('date', 'taglia')):
    """probabilita' che nomi presi a caso (stessa data e taglia, stesso numero) facciano almeno altrettanti successi"""
    x = D[D[okc] & D.taglia.notna()]
    g = x.groupby(list(by), observed=True).agg(N=(tgt, 'size'), K=(tgt, 'sum'), n=(sig, 'sum'))
    g = g[g.n > 0]
    hits = int(x[x[sig]][tgt].sum())
    sims = np.zeros(reps)
    for N, K, n in g[['N', 'K', 'n']].itertuples(index=False):
        sims += rng.hypergeometric(int(K), int(N - K), int(n), size=reps)
    exp = (g.K / g.N * g.n).sum() / g.n.sum()
    return exp, (sims >= hits).mean()


rows = []
TG = [('W5', 'ok12', 4), ('X3', 'ok36', 12), ('L50', 'ok12', 4)]


def misura(D, lab, per, tag, do_t=True, reps=1000):
    for s in SIG:
        r = dict(gruppo=lab, periodo=per, taglia=tag, segnale=s)
        x = D[D.ok12]
        r['n_sig'] = int(x[s].sum()); r['n_tot'] = len(x); r['quota'] = x[s].mean()
        if r['n_sig'] < 20: rows.append(r); continue
        for tgt, okc, step in TG:
            y = D[D[okc]]
            if y[s].sum() < 20: continue
            r[f'{tgt}_sig'] = y[y[s]][tgt].mean(); r[f'{tgt}_uni'] = y[tgt].mean(); r[f'{tgt}_no'] = y[~y[s]][tgt].mean()
            e, p = caso(D, s, tgt, okc, reps)
            r[f'{tgt}_caso'] = e; r[f'{tgt}_p'] = p
            e, p = caso(D, s, tgt, okc, reps, by=('date', 'taglia', 'vq', 'pq'))
            r[f'{tgt}_casoV'] = e; r[f'{tgt}_pV'] = p
            if do_t: r[f'{tgt}_t'], r[f'{tgt}_tmin'] = tnon(D, s, tgt, okc, step)
        r['ecc_sig'] = x[x[s]].ecc.mean(); r['ecc_med_sig'] = x[x[s]].ecc.median(); r['ecc_med_uni'] = x.ecc.median()
        if do_t: r['ecc_t'], r['ecc_tmin'] = tnon(D, s, 'ecc', 'ok12', 4)
        r['X3p_sig'] = D[D.ok36 & D[s]].X3p.mean(); r['X3p_uni'] = D[D.ok36].X3p.mean()
        rows.append(r)


misura(U, 'universo', 'tutti', 'tutte')
for p in ['2006-11', '2012-17', '2018-24']:
    misura(U[U.per == p], 'universo', p, 'tutte')
for tg in ['piccole 0,3-2', 'medie 2-15', 'grandi >15']:
    misura(U[U.taglia == tg], 'universo', 'tutti', tg)
for p in ['2006-11', '2012-17', '2018-24']:
    for tg in ['piccole 0,3-2', 'medie 2-15', 'grandi >15']:
        misura(U[(U.per == p) & (U.taglia == tg)], 'universo', p, tg, do_t=False, reps=300)
R = pd.DataFrame(rows)
R.to_csv(f'{OUT}/tab_universo.csv', index=False)
cols = ['gruppo', 'periodo', 'taglia', 'segnale', 'n_sig', 'quota', 'W5_sig', 'W5_caso', 'W5_p', 'W5_casoV', 'W5_pV', 'W5_t', 'W5_tmin', 'X3_sig', 'X3_caso', 'X3_p', 'X3_casoV', 'X3_pV', 'X3_t',
        'X3p_sig', 'X3p_uni', 'L50_sig', 'L50_caso', 'L50_p', 'L50_casoV', 'L50_pV', 'L50_t', 'ecc_sig', 'ecc_med_sig', 'ecc_med_uni', 'ecc_t', 'ecc_tmin']
print(R[[c for c in cols if c in R]].round(3).to_string())
