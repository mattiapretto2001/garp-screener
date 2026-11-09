# regressioni_06: come aggregare le variabili in un punteggio? Pesi uguali fissati a priori (nessuna stima),
# 8 variabili dei filtri GARP/core in percentili per data x regione: roe, de (basso), fcf_m, revq, epsq, peg (basso), rev_cagr, hi52.
# Aggregazioni (4 varianti): media aritmetica, media geometrica, minimo (anello piu' debole), minimo delle 3 famiglie.
# Universo: settori GARP e capitalizzazione >=2 Mld$ (come il core). Top 30 per data, 2012-2026 e 2015-2026.
# ATTENZIONE: le variabili vengono dal core, disegnato guardando 2012-2026: non e' un test fuori campione.
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
OUT = rc.HERE + '/reg_out'; pd.set_option('display.width', 250)
M = rc.load().reset_index(drop=True)
for c in ['top5_reg', 'bot20_reg', 'crash50']: M[c] = M[c].astype(float)
V = ['roe', 'de', 'fcf_m', 'revq', 'epsq', 'peg', 'rev_cagr', 'hi52']
for v in V:
    p = M['z_' + v] / rc.S12 + 0.5
    M['p_' + v] = p.fillna(0.0 if v in ('peg', 'epsq') else 0.5).clip(0.005, 1)   # peg/eps mancanti = falliti (come nel core)
PV = ['p_' + v for v in V]
M['s_media'] = M[PV].mean(1)
M['s_geom'] = np.exp(np.log(M[PV]).mean(1))
M['s_min'] = M[PV].min(1)
fam = {'crescita': ['p_revq', 'p_epsq', 'p_rev_cagr'], 'qualita': ['p_roe', 'p_de', 'p_fcf_m'], 'prezzo_valore': ['p_hi52', 'p_peg']}
M['s_minfam'] = pd.concat([M[c].mean(1) for c in fam.values()], axis=1).min(1)
M = M[M.date <= '2026-06-30']
U = M[~M.excl_sector & (M.mcap_usd >= 2e9)]
out = {}
for start in ['2011-12-31', '2014-12-31']:
    X = M[M.date >= start]; dd = sorted(X.date.unique()); XU = U[U.date >= start]
    uni = X.groupby('date').r_eur.mean()
    P = {'universo >=2Mld settori GARP': pd.DataFrame({'r': XU.groupby('date').r_eur.mean(), 'turn': 0, 'n': XU.groupby('date').size(),
                                                        'top5': XU.groupby('date').top5_reg.mean(), 'bot20': XU.groupby('date').bot20_reg.mean(), 'crash': XU.groupby('date').crash50.mean()}),
         'core di oggi': rc.port(X, lambda g: g[g.core], dd)}
    for s in ['s_media', 's_geom', 's_min', 's_minfam']:
        P[s] = rc.port(XU, lambda g, s=s: g.nlargest(30, s), dd)
    ST = pd.DataFrame({k: rc.pstats(v, uni) for k, v in P.items()}).T
    for c in ST.columns:
        if c not in ('titoli', 't'): ST[c] = ST[c] * 100
    core_r = P['core di oggi'].r
    ST['vs_core'] = [100 * ((1 + P[k].r).prod() ** (4 / len(core_r)) - (1 + core_r).prod() ** (4 / len(core_r))) for k in P]
    ST['t_vs_core'] = [fv3.nw_t(P[k].r - core_r, 2) for k in P]
    print('DAL', start, '(differenze rispetto all universo di tutti i settori e taglie)'); print(ST.round(2).to_string())
    out[start] = ST
pd.concat(out).to_csv(f'{OUT}/aggregazione.csv')
