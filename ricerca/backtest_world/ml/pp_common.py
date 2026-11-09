# pp_common (07/11, punto 3): risultati attesi degli screener sul SOLO periodo pulito (date 31/03/2018 - 30/09/2026),
# quando i dati EODHD contengono anche le societa' uscite dal listino.
# Riusa scr_common (pannello panel2 + scr_extra, liste e regole del 07/11, NON ritoccate) e prende da features_v3 solo
# le colonne che servono alle regole di sicurezza (diluizione 1 anno corretta per i frazionamenti) e agli esiti (crolli).
#
# REGOLE FISSATE PRIMA DI GUARDARE I RISULTATI DEL PERIODO PULITO:
#  - periodi: 2018-21 = date 31/03/2018-30/09/2021; 2022-24 = 31/12/2021-30/09/2024; 2025-26 = 31/12/2024-30/09/2026
#    (l'ultimo trimestre arriva al 06/11/2026); totale 2018-26. La data e' l'inizio del trimestre di possesso.
#  - liste: quelle di scr_common. Top 30 >= 2 Mld$ come nel repository (abafddf): primi 30 per punteggio GARP fra i
#    promossi >= 2 Mld$, PEG < 0,05 trattato come mancante (vale 50). Radar B come nel repository: fallisce solo il PEG,
#    PEG >= 2 con utile e crescita positivi, >= 2 Mld$.
#  - t: Newey-West con 2 ritardi sulla differenza TRIMESTRALE (rendimenti che non si sovrappongono).
#  - guardia di sicurezza (esclusione): prezzo < 40% del massimo a 52 settimane OPPURE azioni +25% in un anno (dsh1).
#  - stime mancate (retrocessione): al massimo 1 stima battuta nelle ultime 4 trimestrali, con almeno 3 stime note.
#    Variante: ultima trimestrale sotto le stime (surp_last < 0). Nelle liste intere "retrocedere" = togliere dal
#    portafoglio; nella top 30 = mettere in fondo alla classifica (entrano solo se mancano altri nomi).
#  - sopravvivenza simulata: nel periodo pulito tolgo le societa' uscite dal listino entro 3 anni dalla data (come
#    mancano nel 2012-17); variante estrema: tolgo tutte le societa' oggi non piu' quotate.
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from scr_common import *            # F, REB, A, CORE, CR, Q3, RADA, QU, UNI, mc, REG, run, cagr, tstat, maxdd, W0 ...
from tune_common import pct
import fv3
OUT = f'{HERE}/pp_out'; os.makedirs(OUT, exist_ok=True)

V = fv3.load(cols=['t', 'date', 'dsh1', 'dsh3', 'crash50', 'bankrupt12', 'delist12', 'runway_y', 'burner'])
_n0 = len(F)
F = F.merge(V, on=['t', 'date'], how='left')
assert len(F) == _n0, 'righe duplicate nel merge'

PP = {'2018-21': ('2018-03-31', '2021-09-30'), '2022-24': ('2021-12-31', '2024-09-30'), '2025-26': ('2024-12-31', '2026-09-30'),
      '2018-26': ('2018-03-31', '2026-09-30')}
OLDP = {'2012-17': ('2011-12-31', '2017-12-31'), '2012-26': ('2011-12-31', '2026-09-30')}
ALLP = {**PP, **OLDP}
CLEAN = [d for d in REB if d >= pd.Timestamp('2018-03-31')]


def dates(p):
    a, b = ALLP[p]; return [d for d in REB if pd.Timestamp(a) <= d <= pd.Timestamp(b)]


def nw(x, lags=2):
    return fv3.nw_t(pd.Series(x).dropna(), lags=lags)


# ------------------------------------------------------------------ liste (definizioni di scr_common + repository)
B2 = (mc >= 2e9).fillna(False); B5 = (mc >= 5e9).fillna(False)
F['peg_g'] = F.peg.where(F.peg >= 0.05)
WG = {'peg_g': 30, 'revq': 12, 'epsq': 12, 'rev_cagr': 12, 'roe': 12, 'fcfy': 11, 'de': 11}
LOWG = {'peg_g', 'de'}


def score_g(m):
    out = pd.Series(np.nan, index=F.index)
    for t, x in F[m].groupby('date'):
        out[x.index] = sum(w * pct(x[k], k not in LOWG) for k, w in WG.items())
    return out


SC_A2 = score_g(A & B2)


def topn(m, n=30, demote=None, sc=None):
    """primi n per punteggio GARP dentro m; demote = maschera dei nomi da mettere in fondo"""
    sc = SC_A2 if sc is None else sc
    d = F[m].assign(_s=sc[m], _d=(demote[m] if demote is not None else False))
    d = d.sort_values(['date', '_d', '_s'], ascending=[True, True, False]).groupby('date').head(n)
    out = pd.Series(False, index=F.index); out[d.index] = True; return out


TOP30_2B = topn(A & B2)
RADB2 = (UNI & (F.n_fail == 1) & ~F['ok_PEG'] & (F.peg >= 2) & (F.ni_ttm > 0) & B2).fillna(False)
RADB_OLD = UNI & (F.n_fail == 1) & ~F['ok_PEG']                  # definizione del 07/11 (senza soglia di taglia)
RADA_OLD = UNI & ~A & (F.revq > 0.40).fillna(False) & (F.rev_cagr > 0.15).fillna(False) & (F.dshares < 0.10).fillna(True)
SMALL = SIZE3 == 'piccole 0,3-2'; MID = SIZE3 == 'medie 2-15'; LARGE = SIZE3 == 'grandi >15'

# nome -> (maschera della lista, universo di confronto)
LISTS = {
    'GARP larga (PEG<2)': (A, UNI),
    'GARP core': (CORE, UNI),
    'Top 30 >=2 Mld$': (TOP30_2B, UNI),
    'Crescita piccole 0,3-2': (CR & SMALL, UNI & SMALL),
    'Crescita medie 2-15': (CR & MID, UNI & MID),
    'Crescita grandi >15': (CR & LARGE, UNI & LARGE),
    'Crescita >=2 Mld$': (CR & B2, UNI & B2),
    'Qualita Q3': (Q3, QU & B5),
    'Radar A (>=2 Mld$)': (RADA, UNI & B2),
    'Radar B (>=2 Mld$)': (RADB2, UNI & B2),
}
MIX = ('GARP core', 'Qualita Q3')     # 50% core + 50% Q3, confrontato con QU (come scr_04)

# ------------------------------------------------------------------ regole di sicurezza
GUARD = ((F.hi52 < 0.40) | (F.dsh1 > 0.25)).fillna(False)                      # esclusi
MISS = ((F.n_beat4 <= 1) & (F.n_est4 >= 3)).fillna(False)                        # retrocessi (principale)
MISS2 = (F.surp_last < 0).fillna(False)                                          # variante: ultima trimestrale mancata

# ------------------------------------------------------------------ sopravvivenza simulata
LAST = F.t.map(F.groupby('t').date.max())
DEL3 = (F.delisted.astype(bool) & ((LAST - F.date).dt.days <= 3 * 365.25)).fillna(False)
DELALL = F.delisted.astype(bool).fillna(False)


# ------------------------------------------------------------------ motore e misure
def useries(univ):
    return F[univ].groupby('date').r_eur.mean().reindex(REB).fillna(0.0)


def year_ret(r, y):
    ds = [d for d in REB if pd.Timestamp(f'{y - 1}-12-31') <= d <= pd.Timestamp(f'{y}-09-30')]
    return (1 + r[ds]).prod() - 1


def dd_in(r, y):
    ds = [d for d in REB if pd.Timestamp(f'{y - 1}-12-31') <= d <= pd.Timestamp(f'{y}-09-30')]
    w = (1 + r[ds]).cumprod(); return min(0.0, (w / np.maximum.accumulate(np.r_[1.0, w.values])[1:]).min() - 1)


def measure(r, n, m, u, univ, periods=PP, extra=None):
    """r = rendimento netto trimestrale della lista, u = universo (senza costi); m = righe della lista"""
    out = []
    for p in periods:
        ds = dates(p); a, b = ALLP[p]
        sel = F.date.between(pd.Timestamp(a), pd.Timestamp(b))
        X = F[m & sel & F.crash50.notna()]; U = F[univ & sel & F.crash50.notna()]
        exc = (r - u)[ds]
        out.append(dict(periodo=p, n=n.reindex(ds).mean(), cagr=cagr(r, a, b), univ=cagr(u, a, b), diff=cagr(r, a, b) - cagr(u, a, b),
                        t_nw=nw(exc), t=tstat(exc), maxdd=maxdd(r[ds]), u_maxdd=maxdd(u[ds]),
                        crolli=X.crash50.mean(), u_crolli=U.crash50.mean(), perdenti=X.L20.mean(), eccez=X.W5.mean(),
                        n_righe=len(X), **(extra or {})))
    return out


def ev(name, m, univ, periods=PP, tag='Mondo', r=None, n=None):
    if r is None: r, n = run(F, m & univ)
    u = useries(univ)
    o = measure(r, n, m & univ, u, univ, periods, dict(lista=name, regione=tag))
    for y in (2022,):
        for x in o: x.update({f'r{y}': year_ret(r, y), f'u{y}': year_ret(u, y), f'dd{y}': dd_in(r, y), f'udd{y}': dd_in(u, y)})
    return o, r, u


def caso(m, pool, periods=PP, n_it=400, seed=7):
    """quota di estrazioni a caso (stesso numero di titoli per data, dentro pool) battute dalla lista, lordo"""
    rng = np.random.default_rng(seed); R = F.r_eur.values
    ds_all = sorted(set(d for p in periods for d in dates(p)))
    cnt = F[m].groupby('date').size()
    real = F[m].groupby('date').r_eur.mean().reindex(REB).fillna(0.0)
    G = {t: x.index.values for t, x in F[pool].groupby('date')}
    sims = {p: [] for p in periods}
    for it in range(n_it):
        g = pd.Series(0.0, index=REB)
        for t in ds_all:
            k = cnt.get(t, 0); idx = G.get(t, np.array([]))
            if k and len(idx): g[t] = R[rng.choice(idx, min(k, len(idx)), replace=False)].mean()
        for p in periods: sims[p].append(cagr(g, *ALLP[p]))
    res = {}
    for p in periods:
        s = np.array(sims[p]); v = cagr(real, *ALLP[p])
        res[p] = dict(batte=np.mean(s < v), reale_lordo=v, caso_mediana=np.median(s), caso_p5=np.percentile(s, 5), caso_p95=np.percentile(s, 95))
    return res


def pr(a, d=1, sign=True):
    if a is None or pd.isna(a): return 'n.d.'
    return (f'{a * 100:+.{d}f}' if sign else f'{a * 100:.{d}f}').replace('.', ',').replace('-', '−')
