# f3_04 (09/11): portafogli trimestrali a pesi uguali, rendimenti in euro, 0,5% per acquisto o vendita.
# (1) universo per area: quinto alto del segnale vs tutti quelli con il segnale -> rotazione e effetto dei costi.
# (2) dentro le liste (core GARP, GARP, Crescita, Qualita'): meta' alta del segnale (mediana dentro la lista alla data)
#     vs lista intera, e vs 300 scelte a caso dello stesso numero di titoli (confronto al LORDO: il caso ruota quasi al 100%).
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
OUT = f'{HERE}/f3_out'; COST = 0.005
F = pd.read_pickle(f'{OUT}/pannello.pkl')
F = F[F.r_eur.notna()].copy()
DATES = sorted(F.date.unique())
RD = {d: dict(zip(x.t, x.r_eur)) for d, x in F.groupby('date')}
PER = {'2012-26': ('2011-12-31', '2026-09-30'), '2018-26': ('2018-03-31', '2026-09-30')}


def port(sel, cost=COST):
    """sel: dict data -> set di titoli. Ritorna serie trimestrale netta e rotazione media (quota venduta+comprata / 2)."""
    out, turn, prev = {}, [], set()
    for d in DATES:
        k = sel.get(d, set())
        g = np.mean([RD[d][x] for x in k]) if k else 0.0
        sold = len(prev - k) / len(prev) if prev else 0; bought = len(k - prev) / len(k) if k else 0
        out[d] = g - cost * (sold + bought); prev = k
        if k: turn.append((sold + bought) / 2)
    return pd.Series(out), np.mean(turn)


def ann(s, a, b):
    x = s[(s.index >= a) & (s.index <= b)]
    return (1 + x).prod() ** (4 / len(x)) - 1


def sets(mask):
    return {d: set(x.t) for d, x in F[mask].groupby('date')}


rows = []
# (1) universo (anche lordo, per vedere quanto mangiano i costi)
for area in ['USA', 'Resto']:
    A = F.area == area
    for nm, col, hi in [('a SUE', 'rk_sue', None), ('a2 sorpresa %', 'rk_spct', None), ('b EAR', 'rk_ear', None),
                        ('c serie >=4', 'streak', 4), ('d combo', 'combo', 1), ('rif. n_beat4 = 4', 'n_beat4', 4)]:
        has = A & F[col].notna()
        top = has & ((F[col] >= 0.8) if hi is None else (F[col] >= hi))
        st, tt = port(sets(top)); sb, tb = port(sets(has)); stg, _ = port(sets(top), 0.0); sbg, _ = port(sets(has), 0.0)
        for pn, (a, b) in PER.items():
            rows.append(dict(livello='universo', area=area, lista='-', segnale=nm, per=pn, n_medio=F[top].groupby('date').size().mean(),
                             netto_sel=ann(st, a, b), netto_base=ann(sb, a, b), rot_sel=tt, rot_base=tb,
                             diff=ann(st, a, b) - ann(sb, a, b), diff_lorda=ann(stg, a, b) - ann(sbg, a, b), t=fv3.nw_t((st - sb)[(st.index >= a) & (st.index <= b)], 1)))
U = pd.DataFrame(rows)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
print(U.round(3).to_string())

# (2) liste
rng = np.random.default_rng(7)
rows = []
for L in ['L_core', 'L_GARP', 'L_Crescita', 'L_Qualita']:
    M = F[L]
    sb, tb = port(sets(M))
    for nm, col in [('a SUE', 'sue'), ('a2 sorpresa %', 'spct'), ('b EAR', 'ear'), ('c serie >=4', 'streak'), ('rif. n_beat4 = 4', 'n_beat4')]:
        X = F[M & F[col].notna()]
        if nm.startswith('c') or nm.startswith('rif'):
            top = X[X[col] >= 4]
        else:
            top = X[X[col] >= X.groupby('date')[col].transform('median')]
        S = {d: set(x.t) for d, x in top.groupby('date')}
        st, tt = port(S); stg, _ = port(S, cost=0.0); sbg, _ = port(sets(M), cost=0.0)
        # scelte a caso: stesso numero di titoli per data, presi dalla lista intera
        pool = {d: x.t.values for d, x in F[M].groupby('date')}
        kk = {d: len(s) for d, s in S.items()}
        rnd = {pn: [] for pn in PER}
        for i in range(300):
            Sr = {d: set(rng.choice(pool[d], size=min(k, len(pool[d])), replace=False)) for d, k in kk.items() if d in pool}
            sr, _ = port(Sr, cost=0.0)
            for pn, (a, b) in PER.items(): rnd[pn].append(ann(sr, a, b))
        for pn, (a, b) in PER.items():
            v = ann(st, a, b)
            rows.append(dict(lista=L[2:], segnale=nm, per=pn, n_medio=np.mean(list(kk.values())), netto_sel=v, netto_lista=ann(sb, a, b),
                             diff=v - ann(sb, a, b), t=fv3.nw_t((st - sb)[(st.index >= a) & (st.index <= b)], 1),
                             lordo_sel=ann(stg, a, b), lordo_lista=ann(sbg, a, b),
                             caso_lordo_med=np.median(rnd[pn]), pct_caso_lordo=(np.array(rnd[pn]) < ann(stg, a, b)).mean(), rot_sel=tt, rot_lista=tb))
        print(L, nm, flush=True)
Lr = pd.DataFrame(rows)
print(Lr.round(3).to_string())
U.to_csv(f'{OUT}/f3_04_universo.csv', index=False); Lr.to_csv(f'{OUT}/f3_04_liste.csv', index=False)
