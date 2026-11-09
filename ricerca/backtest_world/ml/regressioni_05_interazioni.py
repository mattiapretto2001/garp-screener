# regressioni_05: (1) il core aggiunge informazione oltre alle 37 variabili lineari? (dummy core/GARP in Fama-MacBeth)
# (2) 5 interazioni decise a priori (crescita x momentum/prezzo/redditivita'/valutazione) nell'universo dei settori GARP
# (3) Holm sull'insieme principale (37 variabili x 3 target)  (4) R&S fra le americane in perdita (profilo pre-utile)
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
OUT = rc.HERE + '/reg_out'
pd.set_option('display.width', 250)
log = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.append(s)
M = rc.load(); M = M[M.fwd12_eur.notna()].reset_index(drop=True)
PER = rc.per_of(M.date)
G = rc.GLOBAL; ZG = ['z_' + c for c in G]
S = M[~M.excl_sector].copy()
S[ZG] = rc.rank_z(S, ZG, ['date', 'reg']).values
S['y_rk'] = rc.rank_z(S.assign(f=S.fwd12_eur), ['f'], ['date', 'reg'])['f']
gq = S.groupby(['date', 'reg']).fwd12_eur; rk = (gq.rank() - 0.5) / gq.transform('count')
S['top5'] = (rk >= 0.95) * 100.; S['bot20'] = (rk <= 0.20) * 100.
S['core_d'] = S.core.astype(float); S['garp_d'] = S.GARP.astype(float)
# (1)
for dm in ['core_d', 'garp_d']:
    for y in ['y_rk', 'top5', 'bot20']:
        C = rc.fm(S[['date'] + ZG + [dm, y]], ZG + [dm], y)
        s = rc.summarize(C.iloc[:, [-1]], per=PER).iloc[0]
        say('%s oltre le 37 lineari, target %s: coef %.3f t %.2f | per periodo t %.1f / %.1f / %.1f' % (dm, y, s.coef, s.t, s['t_2012-16'], s['t_2017-21'], s['t_2022-26']))
# (2) interazioni
INT = [('revq', 'hi52'), ('revq', 'roe'), ('rev_cagr', 'mom12_1'), ('revq', 'ev_sales'), ('rev_cagr', 'fcf_m')]
icols = []
for a, b in INT:
    c = f'i_{a}_x_{b}'; S[c] = S['z_' + a].fillna(0) * S['z_' + b].fillna(0); icols.append(c)
res = {}
for y in ['y_rk', 'top5', 'bot20']:
    C = rc.fm(S[['date'] + ZG + icols + [y]], ZG + icols, y)
    res[y] = rc.summarize(C[icols], per=PER)
T = pd.concat({y: r[['coef', 't', 't_2012-16', 't_2017-21', 't_2022-26']] for y, r in res.items()}, axis=1)
say(T.round(3).to_string()); T.to_csv(f'{OUT}/interazioni.csv')
# per regione (solo rango)
for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia']:
    R = S[S.reg_rob == rg].copy()
    R[ZG] = rc.rank_z(R, ZG, ['date']).values; R['y_rk'] = rc.rank_z(R.assign(f=R.fwd12_eur), ['f'], ['date'])['f']
    for a, b in INT: R[f'i_{a}_x_{b}'] = R['z_' + a].fillna(0) * R['z_' + b].fillna(0)
    C = rc.fm(R[['date'] + ZG + icols + ['y_rk']], ZG + icols, 'y_rk', min_n=len(ZG) + 20)
    say(rg, ' '.join('%s t=%.1f' % (c[2:], fv3.nw_t(C[c])) for c in icols))
# (3) Holm sul blocco principale
Sx = pd.read_csv(f'{OUT}/fm_sintesi.csv', index_col=0)
for c in ['holm_rk', 'holm_top5', 'holm_bot20']:
    ok = Sx[Sx[c] < 0.05]
    say('Holm<5%%, %s: %s' % (c, ', '.join(f'{i}(t {ok.loc[i, "t_" + c[5:]]:.1f})' for i in ok.index)))
say('|t|>=3 (soglia Harvey-Liu-Zhu): rk %d, top5 %d, bot20 %d su 37' % ((Sx.t_rk.abs() >= 3).sum(), (Sx.t_top5.abs() >= 3).sum(), (Sx.t_bot20.abs() >= 3).sum()))
# (4) americane in perdita: R&S, margine lordo, spese generali, copertura analisti
U = M[(M.reg == 'USA') & (M.ni_ttm <= 0) & ~M.excl_sector].copy()
XU = ZG + ['z_rd_int', 'z_gm', 'z_sga_int', 'z_n_est4']
U[XU] = rc.rank_z(U, XU, ['date']).values
U['y_rk'] = rc.rank_z(U.assign(f=U.fwd12_eur), ['f'], ['date'])['f']
gq = U.groupby('date').fwd12_eur; rk = (gq.rank() - 0.5) / gq.transform('count')
U['top5'] = (rk >= 0.95) * 100.; U['bot20'] = (rk <= 0.20) * 100.
say('USA in perdita, settori GARP: righe %d, media per data %d' % (len(U), len(U) / U.date.nunique()))
for y in ['y_rk', 'top5', 'bot20', 'crash50']:
    U['crash50'] = U.crash50.astype(float) * 100
    C = rc.fm(U[['date'] + XU + [y]], XU, y); C.columns = [c[2:] for c in XU]
    s = rc.summarize(C, per=PER)
    keep = ['rd_int', 'gm', 'sga_int', 'n_est4', 'cash_mcap', 'ev_sales', 'vol1y', 'hist_y', 'dsh1', 'fcf_m', 'hi52', 'mom12_1']
    say(y, ' | '.join('%s %.1f' % (k, s.loc[k, 't']) for k in keep))
open(f'{OUT}/regressioni_05.log', 'w').write('\n'.join(log))
