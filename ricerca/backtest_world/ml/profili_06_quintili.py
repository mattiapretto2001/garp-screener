# profili_06: portafogli per quintile del punteggio (fuori campione 2015-2026, ogni trimestre, pesi uguali, lordi) contro l'universo del profilo.
# Misura piu' stabile del top 10/20: dice se il punteggio ordina davvero il rendimento composto.
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
pd.set_option('display.width', 250)


def maxdd(r): w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()


rows = []
for k in PNAME:
    for m in SC[k].columns:
        s = SC[k][m].astype(float); X = B.loc[s.index]
        q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
        U = X.groupby('date').r_eur.mean()
        R = {i: X[q == i].groupby('date').r_eur.mean().reindex(U.index).fillna(0) for i in range(1, 6)}
        d = R[5] - U; d1 = R[5] - R[1]
        row = dict(profilo=k, metodo=m, **{f'Q{i}': cagr_q(R[i]) for i in range(1, 6)}, U=cagr_q(U), Q5_U=cagr_q(R[5]) - cagr_q(U),
                   t_Q5_U=d.mean() / d.std() * np.sqrt(len(d)), Q5_Q1=cagr_q(R[5]) - cagr_q(R[1]), t_Q5_Q1=d1.mean() / d1.std() * np.sqrt(len(d1)),
                   dd_Q5=maxdd(R[5]), dd_U=maxdd(U), vol_Q5=R[5].std() * 2, vol_U=U.std() * 2)
        for p, (a, b) in list(OOSP.items())[:3]:
            mk = (U.index.year >= a) & (U.index.year <= b); row[f'Q5_U {p}'] = cagr_q(R[5][mk]) - cagr_q(U[mk])
        # per gruppo di regioni: Q5 contro universo del profilo nel gruppo (quintili rifatti nel gruppo)
        for g in GROUPS:
            Xg = X[X.reg_rob == g]; sg = s[X.reg_rob == g]
            if Xg.groupby('date').size().median() < 25: row[f'Q5_U {g}'] = np.nan; continue
            qg = np.ceil(sg.groupby(Xg.date).rank(pct=True) * 5).clip(1, 5)
            Ug = Xg.groupby('date').r_eur.mean(); r5 = Xg[qg == 5].groupby('date').r_eur.mean().reindex(Ug.index).fillna(0)
            row[f'Q5_U {g}'] = cagr_q(r5) - cagr_q(Ug)
        rows.append(row)
Q = pd.DataFrame(rows); Q.to_csv(f'{OUT}/quintili.csv', index=False)
print(Q[['profilo', 'metodo', 'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'U', 'Q5_U', 't_Q5_U', 'Q5_Q1', 't_Q5_Q1', 'dd_Q5', 'dd_U', 'vol_Q5', 'vol_U']].round(3).to_string(index=False))
print(Q[['profilo', 'metodo'] + [c for c in Q.columns if c.startswith('Q5_U ')]].round(3).to_string(index=False))
