# avv_pp_01: verifica avversariale di R_periodo_pulito_2018_2026.md
# Ricalcolo INDIPENDENTE (motore, CAGR e t scritti qui, non quelli di tune_common/pp_common) delle cifre chiave,
# usando solo le maschere delle liste (CORE, CR, Q3, ...) e il pannello.
import sys, os
ML = '${RICERCA_BASE}/backtest_world/ml'
sys.path.insert(0, ML)
from pp_common import *   # F, REB, CLEAN, maschere
import numpy as np, pandas as pd
END = pd.Timestamp('2026-11-06')
NXT = {t: (REB[i + 1] if i + 1 < len(REB) else END) for i, t in enumerate(REB)}
D18 = [d for d in REB if pd.Timestamp('2018-03-31') <= d <= pd.Timestamp('2026-09-30')]


def port(m, cost=0.005, dates=D18):
    """pesi uguali, costo sulle sole entrate/uscite (come l'autore) -> serie netta"""
    X = F[m & F.date.isin(dates)][['t', 'date', 'r_eur']]
    G = dict(tuple(X.groupby('date')))
    out, prev = {}, set()
    for d in dates:
        x = G.get(d); cur = set(x.t) if x is not None else set()
        g = x.r_eur.mean() if x is not None and len(x) else 0.0
        c = cost * ((len(prev - cur) / len(prev) if prev else 0) + (len(cur - prev) / len(cur) if cur else 0))
        out[d] = g - c; prev = cur
    return pd.Series(out)


def uni(m, dates=D18):
    return F[m & F.date.isin(dates)].groupby('date').r_eur.mean().reindex(dates).fillna(0.0)


def ann(r, dates=D18):
    yrs = (NXT[dates[-1]] - dates[0]).days / 365.25
    return (1 + r.reindex(dates)).prod() ** (1 / yrs) - 1


def nwt(x, L=2):
    x = np.asarray(pd.Series(x).dropna(), float); T = len(x); e = x - x.mean(); v = e @ e / T
    for l in range(1, L + 1): v += 2 * (1 - l / (L + 1)) * (e[l:] @ e[:-l]) / T
    return x.mean() / np.sqrt(v / T)


rows = []
def rep(name, r, u, claimed):
    d = ann(r) - ann(u); t = nwt((r - u).reindex(D18))
    rows.append(dict(lista=name, diff=round(d * 100, 1), t_nw=round(t, 2), dichiarato=claimed))
    print(f'{name:40s} {d*100:+6.1f}  t {t:5.2f}   (rapporto: {claimed})', flush=True)

rc = port(CORE & UNI); u_g = uni(UNI)
rep('core vs universo GARP', rc, u_g, '+15,6 (2,4)')
rep('core vs universo >=2 Mld$ (stessa taglia)', rc, uni(UNI & B2), 'n.d.')
rcr = port(CR & B2 & UNI); rep('Crescita >=2 Mld$', rcr, uni(UNI & B2), '+8,9 (2,0)')
rq = port(Q3 & QU & B5); rep('Qualita Q3', rq, uni(QU & B5), '+3,4 (1,8)')
rmix = 0.5 * rc + 0.5 * rq
rep('misto 50/50 vs QU (tutte le taglie)', rmix, uni(QU), '+9,1 (2,0)')
rep('misto 50/50 vs QU >=2 Mld$', rmix, uni(QU & B2), 'n.d.')
rcs = port(CR & SMALL & UNI); rep('Crescita piccole', rcs, uni(UNI & SMALL), '+10,8 (2,4)')
rra = port(RADA & UNI & B2); rep('Radar A', rra, uni(UNI & B2), '+3,1 (0,9)')

# senza 2020 e 2025 (trimestri di possesso 2020 e 2025 tolti)
NO = [d for d in D18 if not (pd.Timestamp('2019-12-31') <= d <= pd.Timestamp('2020-09-30')) and not (pd.Timestamp('2024-12-31') <= d <= pd.Timestamp('2025-09-30'))]
def ann_q(r, ds): return (1 + r.reindex(ds)).prod() ** (4 / len(ds)) - 1
print('senza 2020 e 2025: core %+.1f  Crescita>=2 %+.1f  misto %+.1f  (rapporto +6,5 / +2,3 / +4,2)' % (
    100 * (ann_q(rc, NO) - ann_q(u_g, NO)), 100 * (ann_q(rcr, NO) - ann_q(uni(UNI & B2), NO)), 100 * (ann_q(rmix, NO) - ann_q(uni(QU), NO))))
# 2018-2024 soltanto (senza il 2025-26 intero)
D1824 = [d for d in D18 if d <= pd.Timestamp('2024-09-30')]
print('solo 2018-24 (senza 2025-26): core %+.1f  Crescita>=2 %+.1f  misto %+.1f  Q3 %+.1f' % (
    100 * (ann_q(rc, D1824) - ann_q(u_g, D1824)), 100 * (ann_q(rcr, D1824) - ann_q(uni(UNI & B2), D1824)),
    100 * (ann_q(rmix, D1824) - ann_q(uni(QU), D1824)), 100 * (ann_q(rq, D1824) - ann_q(uni(QU & B5), D1824))))

# sopravvivenza simulata: core e Crescita piccole senza le uscite entro 3 anni
for nm, m, U in [('core', CORE & UNI, UNI), ('Crescita piccole', CR & SMALL & UNI, UNI & SMALL), ('Crescita >=2', CR & B2 & UNI, UNI & B2)]:
    a = ann(port(m)) - ann(uni(U)); b = ann(port(m & ~DEL3)) - ann(uni(U & ~DEL3))
    print(f'sopravvivenza {nm}: completo {a*100:+.1f}, senza uscite 3 anni {b*100:+.1f}, effetto {100*(b-a):+.1f}')

# guardia: GARP larga e Radar A
for nm, m, U in [('GARP larga', A & UNI, UNI), ('Radar A', RADA & UNI & B2, UNI & B2), ('core', CORE & UNI, UNI)]:
    a = ann(port(m)); b = ann(port(m & ~GUARD))
    rem = F[m & GUARD & F.date.isin(D18) & F.crash50.notna()]
    print(f'guardia {nm}: effetto {100*(b-a):+.1f} punti; righe tolte {len(rem)}, titoli diversi {rem.t.nunique()}, crolli fra i tolti {rem.crash50.mean():.0%} '
          f'({int(rem.crash50.sum())} righe, {rem[rem.crash50 == 1].t.nunique()} titoli)')
pd.DataFrame(rows).to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'avv_pp_out', 'avv_pp_01.csv'), index=False)
