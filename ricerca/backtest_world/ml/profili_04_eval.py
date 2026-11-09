# profili_04: misura fuori campione (2015-2026) dei 4 metodi per profilo.
from profili_common import *
B = pd.read_pickle(f'{OUT}/base.pkl'); SC = pd.read_pickle(f'{OUT}/scores_oos.pkl')
METHODS = ['M0', 'M1', 'M2', 'M3', 'M4', 'M5']; NS = [10, 20]


def per_mask(d, p): a, b = OOSP[p]; return (d.year >= a) & (d.year <= b)


def maxdd(r): w = (1 + r).cumprod(); return (w / w.cummax() - 1).min()


IC_rows, DEC_rows, PF_rows = [], [], []
QR = {}
for k in PNAME:
    S = SC[k]; X = B.loc[S.index]
    U = X.groupby('date').r_eur.mean()                       # universo del profilo, pesi uguali, lordo
    # scelte a caso: distribuzione per (n, periodo)
    rng = np.random.default_rng(5); Rd = {d: g.r_eur.values for d, g in X.groupby('date')}
    sims = {}
    for n in NS:
        draws = np.array([[rng.choice(Rd[d], min(n, len(Rd[d])), replace=False).mean() for d in U.index] for _ in range(300)])
        for p in OOSP:
            msk = per_mask(U.index, p); dd = draws[:, msk]
            sims[(n, p)] = (1 + dd).prod(axis=1) ** (4 / msk.sum()) - 1
    for m in METHODS:
        s = S[m].astype(float)
        # IC fuori campione
        Zr = s.groupby(X.date).rank(pct=True).to_frame('s')
        ic = ic_matrix(Zr, X.rk12_reg, X.date)['s']
        icg = {g: ic_matrix(Zr[X.reg_rob == g], X.rk12_reg[X.reg_rob == g], X.date[X.reg_rob == g], min_n=20)['s'].mean() for g in GROUPS}
        IC_rows.append(dict(profilo=k, metodo=m, ic=ic.mean(), t=nwt(ic), **{p: ic[per_mask(ic.index, p)].mean() for p in list(OOSP)[:3]},
                            anni_pos=(ic.groupby(ic.index.year).mean() > 0).mean(), **icg))
        # decimo migliore
        q = Zr.s >= 0.9; v = X.top5_reg.notna()
        DEC_rows.append(dict(profilo=k, metodo=m, ecc_d10=X.top5_reg[q & v].mean(), dis_d10=X.bot20_reg[q & v].mean(), crollo_d10=X.crash50[q & v].mean(),
                             ecc_prof=X.top5_reg[v].mean(), dis_prof=X.bot20_reg[v].mean(), crollo_prof=X.crash50[v].mean(),
                             ecc_d1=X.top5_reg[(Zr.s < 0.1) & v].mean(), dis_d1=X.bot20_reg[(Zr.s < 0.1) & v].mean()))
        for n in NS:
            r, picks = run_top(X, s, n); QR[(k, m, n)] = r
            idx = np.concatenate([picks[d] for d in picks]); P = X.loc[idx]
            for p in OOSP:
                msk = per_mask(r.index, p)
                rp, up = r[msk], U.reindex(r.index)[msk]
                PF_rows.append(dict(profilo=k, metodo=m, n=n, periodo=p, cagr=cagr_q(rp), univ=cagr_q(up), diff=cagr_q(rp) - cagr_q(up),
                                    t=(rp - up).mean() / (rp - up).std() * np.sqrt(len(rp)), maxdd=maxdd(rp), batte_caso=np.mean(sims[(n, p)] < cagr_q(rp)),
                                    ecc=P.top5_reg[per_mask(P.date.dt, p)].mean(), dis=P.bot20_reg[per_mask(P.date.dt, p)].mean(),
                                    usa_pm=(P.reg_rob[per_mask(P.date.dt, p)] == 'USA piccole/medie').mean(),
                                    mcap_med=P.mcap_usd[per_mask(P.date.dt, p)].median() / 1e9))
    QR[(k, 'UNIV', 0)] = U[U.index.year >= 2015]
IC = pd.DataFrame(IC_rows); DEC = pd.DataFrame(DEC_rows); PF = pd.DataFrame(PF_rows)
IC.to_csv(f'{OUT}/oos_ic.csv', index=False); DEC.to_csv(f'{OUT}/oos_decili.csv', index=False); PF.to_csv(f'{OUT}/oos_portafogli.csv', index=False)
pd.to_pickle(QR, f'{OUT}/oos_rendimenti.pkl')
pd.set_option('display.width', 250)
print(IC.round(3).to_string(index=False)); print(DEC.round(3).to_string(index=False))
W = PF[PF.periodo != '2015-26'].pivot_table(index=['profilo', 'metodo', 'n'], columns='periodo', values='diff', sort=False)
A = PF[PF.periodo == '2015-26'].set_index(['profilo', 'metodo', 'n'])[['cagr', 'univ', 'diff', 't', 'maxdd', 'batte_caso', 'ecc', 'dis', 'usa_pm', 'mcap_med']]
print(pd.concat([W, A], axis=1).round(3).to_string())
