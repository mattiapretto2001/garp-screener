# sint_01_coerenza: CONTROLLO DI COERENZA (non una prova) delle 5 liste "snelle" proposte nel REPORT_punteggi_profili.
# Liste, segni, cancelli e guardie FISSATI qui PRIMA di eseguire (07/11/2026), derivati solo dai risultati verificati dei 5 rapporti.
# Una sola esecuzione, nessuna modifica dopo. Solo 2012-2026 (matrice features_v3); il 2000-2011 non e' letto.
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fv3
from profili_common import profiles, rank_in, ic_series, nwt, cagr_q
import temi_common as tc
OUT = f'{HERE}/sint_out'; os.makedirs(OUT, exist_ok=True)
COST = 0.005
F = fv3.load()
assert F.date.min() >= pd.Timestamp('2011-12-31')
F['hist15'] = F.hist_y.clip(upper=15)
P, ind = profiles(F)
# ---- liste fissate prima (segno: +1 alto = meglio, -1 basso = meglio)
COMMON = {'dsh3': -1, 'hist15': +1, 'hi52': +1, 'n_beat4': +1}
L = {
 'QUAL':    {**COMMON, 'vol1y': -1, 'roic': +1, 'opm_std5': -1, 'fcf_m': +1},
 'GARP':    {**COMMON, 'vol1y': -1, 'roe': +1, 'fcf_m': +1, 'peg': -1},
 'CRESC':   {**COMMON, 'opm_std5': -1, 'runway_y': +1, 'capex_int': -1},
 'PREPROF': {**COMMON, 'runway_y': +1, 'npm': +1},
 'TEMI':    {**COMMON, 'fcf_m': +1},
}
# cancelli: profili gia' provati + GARP con crescita ricavi 4a >10% (regola di oggi) + Temi ex ante (industrie segnalate B o MOM alla data)
G = dict(P)
G['GARP_c'] = P['GARP'] & (F.rev_cagr > 0.10)
fl = pd.read_pickle(f'{HERE}/temi_out/ind_flags2.pkl')[['ind', 'date', 'B', 'MOM']]
fl = fl[fl.B.fillna(False) | fl.MOM.fillna(False)]
key = pd.MultiIndex.from_frame(pd.DataFrame({'ind': tc.norm_ind(F.industry), 'date': F.date}))
flagged = set(zip(fl.ind, fl.date))
G['TEMI_ex'] = pd.Series([k in flagged for k in key], index=F.index) & ~F.sector.astype(str).isin(['Financial Services', 'Real Estate', 'Financials'])
LIST_OF = {'QUAL': 'QUAL', 'GARP': 'GARP', 'GARP_c': 'GARP', 'CRESC': 'CRESC', 'PREPROF': 'PREPROF', 'TEMI': 'TEMI', 'TEMI_ex': 'TEMI'}
GUARD = ~((F.hi52 < 0.40) | (F.dsh1 > 0.25))   # guardia minima (esclusione), fissata prima
SC = pd.read_pickle(f'{HERE}/prof_out/scores_oos.pkl')


def score(X, lst):
    Z = {}
    for c, s in lst.items():
        v = X[c].astype(float) * s
        g = v.groupby(X.date)
        Z[c] = ((g.rank(method='average') - 0.5) / g.transform('count')).fillna(0.5)
    return pd.DataFrame(Z).mean(axis=1)


def quint_stats(X, s, q_hi=5):
    q = np.ceil(s.groupby(X.date).rank(pct=True) * 5).clip(1, 5)
    U = X.groupby('date').r_eur.mean()
    R5 = X[q == 5].groupby('date').r_eur.mean().reindex(U.index).fillna(0)
    R1 = X[q == 1].groupby('date').r_eur.mean().reindex(U.index).fillna(0)
    hiH = X[s.groupby(X.date).rank(pct=True) > 0.5].groupby('date').r_eur.mean().reindex(U.index)
    loH = X[s.groupby(X.date).rank(pct=True) <= 0.5].groupby('date').r_eur.mean().reindex(U.index)
    # costo di rotazione del quinto alto
    mem = X[q == 5].groupby('date').t.apply(set); prev = set(); cost = {}
    for d in U.index:
        k = mem.get(d, set())
        sold = len(prev - k) / len(prev) if prev else 0; bought = len(k - prev) / len(k) if k else 0
        cost[d] = COST * (sold + bought); prev = k
    cost = pd.Series(cost)
    d = R5 - U; dh = hiH - loH
    return dict(Q5_U=cagr_q(R5) - cagr_q(U), t_Q5=d.mean() / d.std() * np.sqrt(len(d)), Q5_U_netto=cagr_q(R5 - cost) - cagr_q(U),
                Q1_U=cagr_q(R1) - cagr_q(U), meta_alta=cagr_q(hiH), meta_bassa=cagr_q(loH), t_meta=dh.mean() / dh.std() * np.sqrt(len(dh)),
                rotazione_q=float(cost.mean() / COST / 2))


rows = []
for gname, lname in LIST_OF.items():
    m = G[gname] & (F.date >= '2015-01-01')
    X = F[m].copy(); s = score(X, L[lname])
    ic = ic_series(s, X.rk12_reg, X.date)
    ic18 = ic[ic.index >= '2018-01-01']
    r = dict(cancello=gname, lista=lname, n_var=len(L[lname]), soc_per_data=int(X.groupby('date').size().median()),
             IC=ic.mean(), t_IC=nwt(ic), IC_dal2018=ic18.mean(), t_IC18=nwt(ic18), **quint_stats(X, s))
    top = s.groupby(X.date).rank(pct=True) > 0.9
    ok = X.rk12_reg.notna()
    r.update(dec_ecc=X.top5_reg[top & ok].mean(), dec_dis=X.bot20_reg[top & ok].mean(), dec_crolli=X.crash50[top & ok].mean(),
             prof_ecc=X.top5_reg[ok].mean(), prof_dis=X.bot20_reg[ok].mean(), prof_crolli=X.crash50[ok].mean())
    # solo volatilita' (riferimento per i crolli)
    sv = -X.vol1y.astype(float); topv = sv.groupby(X.date).rank(pct=True) > 0.9
    r.update(vol_dec_crolli=X.crash50[topv & ok].mean(), vol_dec_ecc=X.top5_reg[topv & ok].mean())
    # confronto con M0 sulle stesse righe (solo cancelli gia' provati)
    if gname in SC and 'M0' in SC[gname].columns:
        m0 = SC[gname]['M0'].reindex(X.index).astype(float)
        ok0 = m0.notna()
        ic0 = ic_series(m0[ok0], X.rk12_reg[ok0], X.date[ok0]); r.update(IC_M0=ic0.mean(), t_IC_M0=nwt(ic0))
        ic1 = ic_series(s[ok0], X.rk12_reg[ok0], X.date[ok0]); r.update(IC_snella_stesse_righe=ic1.mean())
        r.update(corr_M0=float(pd.concat([s, m0], axis=1).dropna().corr(method='spearman').iloc[0, 1]))
    # guardia minima: quota esclusa e crolli fra gli esclusi
    gx = GUARD[X.index]
    r.update(guardia_esclusi=1 - gx.mean(), crolli_esclusi=X.crash50[~gx & ok].mean(), crolli_ammessi=X.crash50[gx & ok].mean(),
             ecc_esclusi=X.top5_reg[~gx & ok].mean())
    # periodi
    for a, b in [('2015', '2017'), ('2018', '2021'), ('2022', '2026')]:
        icp = ic[(ic.index >= f'{a}-01-01') & (ic.index <= f'{b}-12-31')]; r[f'IC_{a}-{b}'] = icp.mean()
    rows.append(r)
T = pd.DataFrame(rows)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
print(T.round(3).T.to_string())
T.to_csv(f'{OUT}/coerenza_liste_snelle.csv', index=False)
