# regressioni_01: Fama-MacBeth trimestrali (OLS sui ranghi), modelli di probabilita' lineari e logit per data,
# per periodo, per regione, blocco solo-USA e sotto-popolazioni dei profili. Solo date 2011-12..2025-09 (target 12m noto).
import sys, os, time, warnings, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
from sklearn.linear_model import LogisticRegression
warnings.filterwarnings('ignore')
T0 = time.time(); OUT = rc.HERE + '/reg_out'; os.makedirs(OUT, exist_ok=True)
M = rc.load(); M = M[M.fwd12_eur.notna()].reset_index(drop=True)
PER = rc.per_of(M.date)
G = rc.GLOBAL; ZG = ['z_' + c for c in G]
P = fv3.PREDICTORS; ZP = ['z_' + c for c in P]
M['y_rk'] = (M.rk12_reg - 0.5) * rc.S12
# eccesso in % winsorizzato 1-99 per data (per le grandezze in punti percentuali)
M['y_xs'] = fv3.winsor(M.assign(xs=M.xs12_reg), ['xs'])['xs'] * 100
for c in ['top5_reg', 'bot20_reg', 'crash50']: M[c] = M[c].astype(float) * 100   # in punti percentuali
log = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s); log.append(s)

# ---------------- A. VIF
X = M[ZG].fillna(0).values
v_g = pd.Series(rc.vif(X), index=G)
v_all = pd.Series(rc.vif(M[ZP].fillna(0).values), index=P)
say('VIF set mondiale (37): mediana %.2f max %.2f (%s)' % (v_g.median(), v_g.max(), v_g.idxmax()))
say('VIF tutte le 81: mediana %.2f, >5: %d, >10: %d, max %.1f (%s)' % (v_all.median(), (v_all > 5).sum(), (v_all > 10).sum(), v_all.max(), v_all.idxmax()))
pd.DataFrame({'vif_set37': v_g, 'vif_81': v_all}).to_csv(f'{OUT}/vif.csv')

# ---------------- B. FM univariata (tutte le 81, target rango) -> confronto marginale vs parziale
uni = {}
for c in P:
    C = rc.fm(M[['date', 'z_' + c, 'y_rk']], ['z_' + c], 'y_rk', min_n=100)
    uni[c] = (C.iloc[:, 0].mean(), fv3.nw_t(C.iloc[:, 0]))
uni = pd.DataFrame(uni, index=['coef', 't']).T
uni.to_csv(f'{OUT}/fm_univariata.csv')
say('Univariate (81): |t|>2: %d, |t|>3: %d' % ((uni.t.abs() > 2).sum(), (uni.t.abs() > 3).sum()))

# ---------------- C-E. FM multivariata, universo mondiale
res = {}
for y in ['y_rk', 'y_xs', 'top5_reg', 'bot20_reg', 'crash50']:
    C = rc.fm(M[['date'] + ZG + [y]], ZG, y); C.columns = G
    C.to_pickle(f'{OUT}/fm_coef_{y}.pkl')
    res[y] = rc.summarize(C, per=PER)
    res[y].to_csv(f'{OUT}/fm_{y}.csv')
# R2 medio per data (OLS rango)
r2 = []
for d, g in M.groupby('date'):
    Xd = np.column_stack([np.ones(len(g)), g[ZG].fillna(0).values]); yd = g.y_rk.values
    b, *_ = np.linalg.lstsq(Xd, yd, rcond=None); e = yd - Xd @ b
    r2.append(1 - e.var() / yd.var())
say('R2 medio per data (37 variabili, rango): %.3f (min %.3f max %.3f)' % (np.mean(r2), np.min(r2), np.max(r2)))

# logit per data (top5_reg, bot20_reg, crash50) - coefficienti in log-odds per 1 dev. std
lg = {}
for y in ['top5_reg', 'bot20_reg', 'crash50']:
    rows = {}
    for d, g in M.groupby('date'):
        yy = (g[y].values > 50).astype(int)
        if yy.sum() < 15: continue
        m = LogisticRegression(C=10, max_iter=2000).fit(g[ZG].fillna(0).values, yy)
        rows[d] = m.coef_[0]
    C = pd.DataFrame(rows, index=G).T
    lg[y] = rc.summarize(C, per=PER); lg[y].to_csv(f'{OUT}/logit_{y}.csv')
say('logit fatti', round(time.time() - T0))

# ---------------- F. per regione (ranghi rifatti dentro data x reg_rob)
reg_res = {}
for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia', 'Altri']:
    S = M[M.reg_rob == rg].copy()
    Zs = rc.rank_z(S, ZG, ['date'])   # dentro il gruppo, per data (z gia' col segno; ogni gruppo sta dentro una sola reg)
    S[ZG] = Zs.values
    S['y_rk'] = rc.rank_z(S.assign(f=S.fwd12_eur), ['f'], ['date'])['f']
    gq = S.groupby('date').fwd12_eur
    rk = (gq.rank() - 0.5) / gq.transform('count')
    S['top5'] = (rk >= 0.95) * 100.; S['bot20'] = (rk <= 0.20) * 100.
    for y in ['y_rk', 'top5', 'bot20']:
        C = rc.fm(S[['date'] + ZG + [y]], ZG, y, min_n=len(ZG) + 15); C.columns = G
        reg_res[(rg, y)] = rc.summarize(C)
    say('regione', rg, len(S), round(time.time() - T0))
pd.concat({f'{a}|{b}': v for (a, b), v in reg_res.items()}, axis=1).to_csv(f'{OUT}/fm_regioni.csv')

# ---------------- G. blocco solo-USA (37 + 10 campi estesi)
U = M[M.reg == 'USA'].copy()
GU = G + rc.USBLOCK; ZU = ['z_' + c for c in GU]
us = {}
for y in ['y_rk', 'top5_reg', 'bot20_reg']:
    C = rc.fm(U[['date'] + ZU + [y]], ZU, y); C.columns = GU
    us[y] = rc.summarize(C, per=PER)
pd.concat(us, axis=1).to_csv(f'{OUT}/fm_usa_blocco.csv')
vu = pd.Series(rc.vif(U[ZU].fillna(0).values), index=GU)
say('VIF blocco USA 47: mediana %.2f max %.2f (%s)' % (vu.median(), vu.max(), vu.idxmax()))

# ---------------- H. sotto-popolazioni dei profili (ranghi e target rifatti dentro la sotto-popolazione, data x reg)
pops = {
    'GARP_univ': ~M.excl_sector,
    'profittevoli': (~M.excl_sector) & (M.ni_ttm > 0) & (M.fcf_ttm > 0),
    'crescita20': (~M.excl_sector) & (M.revg_ttm >= 0.20),
    'in_perdita': (~M.excl_sector) & (M.ni_ttm <= 0),
}
sub = {}
for k, msk in pops.items():
    S = M[msk].copy()
    S[ZG] = rc.rank_z(S, ZG, ['date', 'reg']).values
    S['y_rk'] = rc.rank_z(S.assign(f=S.fwd12_eur), ['f'], ['date', 'reg'])['f']
    gq = S.groupby(['date', 'reg']).fwd12_eur
    rk = (gq.rank() - 0.5) / gq.transform('count')
    S['top5'] = (rk >= 0.95) * 100.; S['bot20'] = (rk <= 0.20) * 100.
    S['crash50'] = S['crash50']
    for y in ['y_rk', 'top5', 'bot20', 'crash50']:
        C = rc.fm(S[['date'] + ZG + [y]], ZG, y); C.columns = G
        sub[(k, y)] = rc.summarize(C, per=PER)
    say('popolazione', k, len(S), 'righe, media per data', round(len(S) / S.date.nunique()), round(time.time() - T0))
pd.concat({f'{a}|{b}': v for (a, b), v in sub.items()}, axis=1).to_csv(f'{OUT}/fm_popolazioni.csv')

# ---------------- tabella riassuntiva principale
T = pd.DataFrame({'fam': [rc.FAM[c] for c in G], 'dir': [fv3.DIRECTION[c] for c in G]}, index=G)
T['uni_t'] = uni.loc[G, 't']
for y, nm in [('y_rk', 'rk'), ('y_xs', 'xs'), ('top5_reg', 'top5'), ('bot20_reg', 'bot20'), ('crash50', 'crash')]:
    T[nm] = res[y].coef; T['t_' + nm] = res[y].t
for p in fv3.PER3: T['rk_' + p] = res['y_rk']['t_' + p]
for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia', 'Altri']:
    T['t_' + rg] = reg_res[(rg, 'y_rk')].t
T['lg_top5'] = lg['top5_reg'].coef; T['t_lg_top5'] = lg['top5_reg'].t
T['lg_bot20'] = lg['bot20_reg'].coef; T['t_lg_bot20'] = lg['bot20_reg'].t
sgn = np.sign(T.rk)
T['coerenza'] = sum((np.sign(res['y_rk'][p]) == sgn).astype(int) for p in fv3.PER3) + \
    sum((np.sign(reg_res[(rg, 'y_rk')].coef) == sgn).astype(int) for rg in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia'])
allt = pd.concat([T.t_rk, T.t_top5, T.t_bot20])
p, adj = rc.holm(allt.values)
T['holm_rk'] = adj[:len(G)]; T['holm_top5'] = adj[len(G):2 * len(G)]; T['holm_bot20'] = adj[2 * len(G):]
T.to_csv(f'{OUT}/fm_sintesi.csv')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
say(T[['fam', 'dir', 'uni_t', 'rk', 't_rk', 'xs', 't_xs', 'top5', 't_top5', 'bot20', 't_bot20', 't_crash', 'coerenza', 'holm_rk']].round(3).sort_values('t_rk').to_string())
say(T[['rk_2012-16', 'rk_2017-21', 'rk_2022-26', 't_USA grandi', 't_USA piccole/medie', 't_Europa', 't_Asia', 't_Altri', 't_lg_top5', 't_lg_bot20']].round(1).to_string())
open(f'{OUT}/regressioni_01.log', 'w').write('\n'.join(log))
say('fine', round(time.time() - T0))
