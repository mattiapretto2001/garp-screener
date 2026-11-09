# Prova A (08/11/2026): funzioni comuni. prep / dedup / finish sono copiate senza modifiche da s5_10_universo_v2.py
# (s5_10 esegue tutto all'import), cosi' l'universo v2 ricostruito dal pannello coincide con storico5/universo_prezzi_us_v2.pkl.
import pandas as pd, numpy as np
SRC_ORD = {'A': 0, 'D': 1, 'V': 2, 'W': 3}


def prep(D):
    D = D[D.date <= '2024-09-30'].copy()
    D['anno'] = (D.date + pd.Timedelta(days=1)).dt.year
    D['blocco'] = pd.cut(D.anno, [1999, 2003, 2007, 2011, 2016, 2020, 2025],
                         labels=['2000-03', '2004-07', '2008-11', '2012-16', '2017-20', '2021-25'])
    D['storico'] = D.anno <= 2011
    D['turn'] = D.dv63 / D.cap
    D.loc[(D.cap < 1e7) | (D.cap > 5e12), ['cap', 'turn']] = np.nan
    D['titolo_speciale'] = D.t.str.contains(r'-(?:WS|WT|W|U|UN|R|RT)(?:-[A-Z]{1,2})?$|-R-W$', regex=True)
    base = (D.px >= 3) & (D.dv63 >= 3e6) & (D.n1y >= 200) & D.p52.notna() & D.f12.notna() & ~D.titolo_speciale
    Q = pd.DataFrame({'q1_tetto': D.a_tetto.astype(bool), 'q2_ferma': D.vol < 0.01, 'q3_scambi': D.dv63 > 2e10,
                      'q4_prezzo': (D.px > 5000) & (D.t != 'BRK-A')})
    D['qualita_ko'] = Q.any(axis=1)
    med_turn = D[base & ~D.qualita_ko & D.turn.between(1e-5, 0.5)].groupby('date').turn.median()
    D['cap_est'] = D.dv63 / D.date.map(med_turn)
    D['cap_use'] = D.cap.where(D.cap.notna(), D.cap_est)
    D['cap_vera'] = D.cap.notna()
    return D, base, Q


def dedup(U, nser):
    U = U.sort_values(['date', 'src']).drop_duplicates(['date', 'px', 'dv63']).copy()
    n_a = len(U)
    U['_o'] = U.src.map(SRC_ORD); U['_n'] = -U.t.map(nser)
    U = U.sort_values(['date', '_o', '_n'])
    U['_k'] = U.f12.round(3).astype(str) + '|' + U.p52.round(2).astype(str)
    C = U[U.duplicated(['date', '_k'], keep=False)]
    drop, of = [], []
    for _, g in C.groupby(['date', '_k'], sort=False):
        kept = []
        for i, p, t in zip(g.index, g.px.values, g.t.values):
            j = next((k for q, k in kept if abs(p / q - 1) < 0.005), None)
            if j is None: kept.append((p, t))
            else: drop.append(i); of.append(j)
    dup_of = U.loc[drop, ['t', 'date']].assign(tenuto=of)
    U = U.drop(index=drop).drop(columns=['_o', '_n', '_k'])
    return U, n_a, dup_of


def finish(U):
    U = U.copy()
    U['pct'] = U.groupby('date').f12.rank(pct=True)
    U['L50'] = U.f12 <= -0.5; U['L20'] = U.pct <= 0.2; U['W5'] = U.pct >= 0.95
    U['uscita'] = U.f12_end
    return U


def build(D):
    """universo v2 (regole di s5_10) da un pannello"""
    D, base, Q = prep(D)
    nser = D.groupby('t').size()
    Upre = D[base & ~D.qualita_ko & (D.cap.isna() | (D.cap >= 300e6))]
    U, _, _ = dedup(Upre, nser)
    return finish(U)
