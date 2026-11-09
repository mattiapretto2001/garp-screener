# avv_reg_05: (1) R&S nel blocco USA: mancante = mediana vs mancante = zero, senza sanita', >=2 Mld$, senza controlli di margine;
# (2) cassa/capitalizzazione sulle eccezionali: per periodo, senza sanita', senza l'1% migliore; (3) aggregazioni: le differenze
# fra media aritmetica, geometrica e minimo sono significative?; (4) core senza Asia.
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
warnings.filterwarnings('ignore')
M = rc.load().reset_index(drop=True)
F = fv3.load(cols=['rd_int', 'sector_n', 'rd_ttm', 'rev_ttm'])
M['rd_raw'] = F.rd_int.values; M['sec'] = F.sector_n.astype(str).values
M1 = M[M.fwd12_eur.notna()].copy()
G = rc.GLOBAL; ZG = ['z_' + c for c in G]
PER = rc.per_of(M1.date)
def prep(S, by, xcols):
    S = S.copy(); S[xcols] = rc.rank_z(S, xcols, list(by)).values
    S['y_rk'] = rc.rank_z(S.assign(f=S.fwd12_eur), ['f'], list(by))['f']
    gq = S.groupby(list(by)).fwd12_eur; rk = (gq.rank() - 0.5) / gq.transform('count')
    S['top5'] = (rk >= 0.95) * 100.; S['bot20'] = (rk <= 0.20) * 100.
    return S
def show(S, xcols, name, keys, ys=('y_rk', 'top5', 'bot20'), per=False):
    parts = []
    for y in ys:
        C = rc.fm(S[['date'] + xcols + [y]], xcols, y)
        s = '%s: ' % y + ', '.join('%s %.1f' % (k[2:], fv3.nw_t(C[k])) for k in keys)
        if per:
            s += ' [' + '/'.join('%.1f' % fv3.nw_t(C[k][[PER.get(d) == p for d in C.index]]) for k in keys for p in fv3.PER3) + ']'
        parts.append(s)
    print('%-58s n/data %4d | %s' % (name, len(S) / S.date.nunique(), ' || '.join(parts)))
print('--- (1) R&S/ricavi, blocco USA (37 + 10 campi estesi)')
U = M1[M1.reg == 'USA'].copy()
XU = ZG + ['z_' + c for c in rc.USBLOCK]
U2 = U.copy(); U2['y_rk'] = (U2.rk12_reg - 0.5) * rc.S12; U2['top5'] = U2.top5_reg.astype(float) * 100; U2['bot20'] = U2.bot20_reg.astype(float) * 100
show(U2, XU, 'riproduzione (ranghi per data x regione, mancante=mediana)', ['z_rd_int'], per=True)
print('  quota righe USA con R&S mancante: %.2f' % U.rd_raw.isna().mean())
U3 = U.copy(); U3['rd0'] = U3.rd_raw.fillna(0.0)
U3['z_rd_int'] = rc.rank_z(U3, ['rd0'], ['date'])['rd0']
show(prep(U3, ['date'], [c for c in XU if c != 'z_rd_int']), XU, 'R&S mancante = 0 (rango con gli zeri)', ['z_rd_int'])
show(prep(U[U.sec != 'Healthcare'], ['date'], XU), XU, 'senza sanita', ['z_rd_int'])
show(prep(U[U.mcap_usd >= 2e9], ['date'], XU), XU, '>=2 Mld$', ['z_rd_int'])
show(prep(U[U.rd_raw.notna()], ['date'], XU), XU, 'solo societa che dichiarano R&S', ['z_rd_int'])
MARG = ['z_fcf_m', 'z_opm_avg5', 'z_ey', 'z_fcfy', 'z_roe', 'z_n_loss_5y', 'z_accruals', 'z_gm', 'z_gpa', 'z_sga_int']
show(prep(U, ['date'], XU), [c for c in XU if c not in MARG], 'senza variabili di margine/redditivita', ['z_rd_int'])
Uu = prep(U, ['date'], ['z_rd_int']); show(Uu, ['z_rd_int'], 'R&S da sola', ['z_rd_int'])
print('\n--- (2) cassa/capitalizzazione')
B = M1.copy(); B['y_rk'] = (B.rk12_reg - 0.5) * rc.S12; B['top5'] = B.top5_reg.astype(float) * 100; B['bot20'] = B.bot20_reg.astype(float) * 100
show(B, ZG, 'riproduzione (per periodo fra [])', ['z_cash_mcap'], ys=('top5', 'bot20'), per=True)
show(prep(M1[M1.sec != 'Healthcare'], ['date', 'reg'], ZG), ZG, 'senza sanita', ['z_cash_mcap'], ys=('top5', 'bot20'))
show(prep(M1[~M1.sec.isin(['Healthcare', 'Technology'])], ['date', 'reg'], ZG), ZG, 'senza sanita e tecnologia', ['z_cash_mcap'], ys=('top5', 'bot20'))
for v in ['rev_cagr', 'accruals', 'mom12_1']:
    show(B, ZG, 'riproduzione %s' % v, ['z_' + v], ys=('top5', 'bot20'), per=True)
print('\n--- (3) aggregazioni (variabili del core, settori GARP >=2 Mld$, top 30, 2012-2026): differenze a coppie')
V = ['roe', 'de', 'fcf_m', 'revq', 'epsq', 'peg', 'rev_cagr', 'hi52']
for c in ['top5_reg', 'bot20_reg', 'crash50']: M[c] = M[c].astype(float)
for v in V:
    p = M['z_' + v] / rc.S12 + 0.5
    M['p_' + v] = p.fillna(0.0 if v in ('peg', 'epsq') else 0.5).clip(0.005, 1)
PV = ['p_' + v for v in V]
M['s_media'] = M[PV].mean(1); M['s_geom'] = np.exp(np.log(M[PV]).mean(1)); M['s_min'] = M[PV].min(1)
fam = {'c': ['p_revq', 'p_epsq', 'p_rev_cagr'], 'q': ['p_roe', 'p_de', 'p_fcf_m'], 'p': ['p_hi52', 'p_peg']}
M['s_minfam'] = pd.concat([M[c].mean(1) for c in fam.values()], axis=1).min(1)
X = M[M.date <= '2026-06-30']; dd = sorted(X.date.unique()); XU = X[~X.excl_sector & (X.mcap_usd >= 2e9)]
R = {s: rc.port(XU, lambda g, s=s: g.nlargest(30, s), dd).r for s in ['s_media', 's_geom', 's_min', 's_minfam']}
R['core'] = rc.port(X, lambda g: g[g.core], dd).r
for a, b in [('s_geom', 's_media'), ('s_min', 's_media'), ('s_minfam', 's_media'), ('s_geom', 's_min')]:
    d = R[a] - R[b]
    print('  %s - %s: %+.1f punti/anno, t %.2f' % (a, b, 100 * ((1 + R[a]).prod() ** (4 / len(d)) - (1 + R[b]).prod() ** (4 / len(d))), fv3.nw_t(d, 2)))
print('\n--- (4) core 2015-2026 senza Asia / solo USA')
W = M[(M.date >= '2014-12-31') & (M.date <= '2026-06-30')]; dd = sorted(W.date.unique()); uni = W.groupby('date').r_eur.mean()
for nm, fn in [('core', lambda g: g[g.core]), ('core senza Asia', lambda g: g[g.core & (g.reg != 'Asia')]), ('core solo USA', lambda g: g[g.core & (g.reg == 'USA')])]:
    s = rc.pstats(rc.port(W, fn, dd), uni)
    print('  %-16s titoli %.0f CAGR %.1f%% diff %+.1f t %.2f | %+.1f / %+.1f / %+.1f' % (nm, s['titoli'], s['CAGR'] * 100, s['diff'] * 100, s['t'], s['2015-16'] * 100, s['2017-21'] * 100, s['2022-26'] * 100))
