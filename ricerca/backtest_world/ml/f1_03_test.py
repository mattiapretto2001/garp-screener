# F1 passo 3: prova delle variabili dello studio (regole in f1_common.py, fissate prima) su
#  A) mondo 2012-2026 (features_v3, societa' uscite comprese), periodo pulito dal 31/03/2018;
#  B) USA 2004-2011 solo societa' con bilanci (matrice_B: in pratica sopravvissute -> distorsione dichiarata).
import pandas as pd, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f1_common import *
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
LOG = []
def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.append(s)
NV = 0   # varianti provate (selezione x target x campione), contate a mano qui sotto

# ------------------------------------------------------------------ A) mondo 2012-2026
cols = ['t', 'date', 'reg', 'reg_rob', 'per3', 'excl_sector', 'fcfy', 'pb', 'ev', 'mcap', 'fx_rep', 'equity', 'ni_ttm', 'ta',
        'asset_g', 'ebitda_ttm', 'mom3', 'mom6', 'x3', 'top5_reg', 'bot20_reg', 'crash50', 'fwd12_eur', 'fwd36_eur', 'core']
F = pd.read_pickle(f'{ML}/features_v3.pkl')[cols]
F = F.merge(pd.read_pickle(f'{OUT}/pr_2012.pkl'), on=['t', 'date'], how='left')
F = F.merge(pd.read_pickle(f'{OUT}/liste.pkl'), on=['t', 'date'], how='left')
for k in ['CORE', 'CR', 'Q3', 'RADA', 'A']: F[k] = F[k].fillna(False).astype(bool)
F = add_vars(F, 'reg').reset_index(drop=True)
F['pulito'] = F.date >= '2018-03-31'
F['rate_up'] = F.date.map(fed_rising)
TG = ['x3', 'top5_reg', 'bot20_reg', 'crash50']
STEP = {'x3': 12, 'top5_reg': 4, 'bot20_reg': 4, 'crash50': 4}
ALL = pd.Series(True, index=F.index)
P('copertura componenti (righe):', {c: round(F[c].notna().mean(), 3) for c in ['fcfy', 'bm', 'size', 'roa', 'inv', 'prange', 'mom3', 'mom6']})
P('quota inv=1 (attivo cresce piu\' dell\'EBITDA):', round(F.inv.mean(), 3))


def row(F, sel, pool, label, group='reg', do_rand=True):
    out = {'selezione': label}
    for tg in TG:
        X = F[pool & F[tg].notna()]
        s = sel[X.index]
        a, b = X.loc[s, tg].mean(), X[tg].mean()
        out[f'{tg}'] = a; out[f'{tg}_base'] = b
        d = X[s].groupby('date')[tg].mean() - X.groupby('date')[tg].mean()
        out[f'{tg}_t'] = nov_t(d, STEP[tg])[0]
        if do_rand and tg in ('x3', 'top5_reg'):
            out[f'{tg}_pcaso'] = rand_pct(F, sel, pool, tg, group)[1]
    out['n_medio'] = F[sel & pool].groupby('date').size().mean()
    return out


def show(rows, title):
    T = pd.DataFrame(rows)
    P(f'\n### {title}')
    P(T.round(4).to_string(index=False))
    return T


# 1) singole variabili: quinto alto (direzione dello studio) contro universo, 2012-2026
R = []
for c in ['fcfy', 'bm', 'size', 'roa', 'prange', 'mom3', 'mom6', 'asset_g']:
    q = F.groupby(['date', 'reg'])[f'k_{c}'].rank(pct=True, method='first') > 0.8
    q &= F[c].notna()
    R.append(row(F, q, ALL, c, do_rand=False)); NV += 4
R.append(row(F, F.inv == 0, ALL, 'inv=0 (attivo coperto da EBITDA)', do_rand=False)); NV += 4
R.append(row(F, F.inv == 1, ALL, 'inv=1 (attivo > EBITDA)', do_rand=False))
T1 = show(R, '1) singole variabili, quinto favorito dallo studio, mondo 2012-26')

# 2) punteggio S per quinti
R = [row(F, F.qS == q, ALL, f'quinto {q} di S', do_rand=(q == 5)) for q in [1, 2, 3, 4, 5]]; NV += 4
T2 = show(R, '2) punteggio studio S per quinti, mondo 2012-26')

# 3) Q5 per periodo e regione
R = []
for lab, m in [('2012-16', F.per3 == '2012-16'), ('2017-21', F.per3 == '2017-21'), ('2022-26', F.per3 == '2022-26'),
               ('pulito 2018+', F.pulito)] + [(g, F.reg_rob == g) for g in ['USA grandi', 'USA piccole/medie', 'Europa', 'Asia', 'Altri']] + \
              [('pulito, solo settori GARP', F.pulito & ~F.excl_sector)]:
    r = row(F, F.qS == 5, m, lab); R.append(r)
T3 = show(R, '3) quinto alto di S per periodo e regione')

# 4) dentro le liste: meta' con S sopra la mediana della lista contro meta' sotto
R = []
for k, nome in [('CORE', 'GARP core'), ('CR', 'Crescita'), ('Q3', 'Qualita Q3'), ('RADA', 'Radar A'), ('A', 'GARP largo')]:
    L = F[k]
    med = F[L].groupby('date').S.transform('median')
    hi = pd.Series(False, index=F.index); hi[med.index] = F.loc[med.index, 'S'] >= med
    for per, pm in [('2012-26', ALL), ('pulito 2018+', F.pulito)]:
        R.append(row(F, hi & L, L & pm, f'{nome} meta\' alta S [{per}]'))
        R.append(row(F, L, pm, f'{nome} lista intera vs universo [{per}]', do_rand=False))
        NV += 4
    R.append(row(F, (F.qS == 5) & L, L, f'{nome} & quinto alto S (vs lista)', do_rand=False)); NV += 4
T4 = show(R, '4) dentro le liste')

# 5) tassi: Fed salita nei 12 mesi prima della data (solo USA, variabile di mercato)
U = F[F.reg == 'USA']
P('\n### 5) tassi (USA 2012-26): Fed salita nei 12 mesi prima della data')
g = U.groupby('date').agg(x3=('x3', 'mean'), crash=('crash50', 'mean'), f12=('fwd12_eur', 'mean'), up=('rate_up', 'first'))
g5 = U[U.qS == 5].groupby('date').agg(x3_q5=('x3', 'mean'), f12_q5=('fwd12_eur', 'mean'))
g = g.join(g5)
P(g.groupby('up')[['x3', 'crash', 'f12', 'x3_q5', 'f12_q5']].mean().round(4).to_string())
P('date con tasso in salita:', int(g.up.sum()), 'su', len(g)); NV += 2
T5 = g

pd.to_pickle(dict(T1=T1, T2=T2, T3=T3, T4=T4, T5=T5), f'{OUT}/tab_2012.pkl')

# ------------------------------------------------------------------ B) USA 2004-2011, solo con bilanci
B = pd.read_pickle(f'{ML}/storico5/provaB/matrice_B.pkl')
B = B.merge(pd.read_pickle(f'{OUT}/pr_f36_2004.pkl'), on=['t', 'date'], how='left')
B['x3'] = (B.f36 >= 2).astype(float).where(B.f36.notna())
B['reg'] = 'USA'
B = add_vars(B, 'reg').reset_index(drop=True)
B['rate_up'] = B.date.map(fed_rising)
# salti finti segnalati dalla verifica della prova B: esclusi dai target a 12 mesi
try:
    FL = pd.read_pickle(f'{ML}/avv_B_out/flag_salti_finti.pkl')
    B = B.merge(FL, on=['t', 'date'], how='left')
    if 'bad12' in B:
        for tg in ['top5_reg', 'bot20_reg', 'crash50']: B.loc[B.bad12.fillna(False).astype(bool), tg] = np.nan
    P('\nrighe B con salti finti escluse (12 mesi):', int(B.get('bad12', pd.Series(dtype=float)).fillna(False).astype(bool).sum()))
except Exception as e:
    P('flag salti non letti:', e)
ALLB = pd.Series(True, index=B.index)
B['core'] = B.core.fillna(False).astype(bool)
R = []
for c in ['fcfy', 'bm', 'size', 'roa', 'prange', 'mom3', 'mom6', 'asset_g']:
    q = (B.groupby('date')[f'k_{c}'].rank(pct=True, method='first') > 0.8) & B[c].notna()
    R.append(row(B, q, ALLB, c, do_rand=False)); NV += 4
R.append(row(B, B.inv == 0, ALLB, 'inv=0', do_rand=False)); NV += 4
for q in [1, 2, 3, 4, 5]: R.append(row(B, B.qS == q, ALLB, f'quinto {q} di S', do_rand=(q == 5)))
NV += 4
for lab, m in [('2004-07 (entrata)', B.date <= '2007-12-31'), ('2008-11 (entrata)', B.date > '2007-12-31')]:
    R.append(row(B, B.qS == 5, m, f'Q5 {lab}'))
med = B[B.core].groupby('date').S.transform('median')
hi = pd.Series(False, index=B.index); hi[med.index] = B.loc[med.index, 'S'] >= med
R.append(row(B, hi & B.core, B.core, 'core GARP meta\' alta S'))
R.append(row(B, B.core, ALLB, 'core GARP vs universo B', do_rand=False)); NV += 4
TB = show(R, 'B) USA 2004-2011, solo societa\' con bilanci (sopravvissute)')
gB = B.groupby('date').agg(x3=('x3', 'mean'), crash=('crash50', 'mean'), f12=('f12', 'mean'), up=('rate_up', 'first'))
P('\nB tassi:'); P(gB.groupby('up')[['x3', 'crash', 'f12']].mean().round(4).to_string())
pd.to_pickle(dict(TB=TB, gB=gB), f'{OUT}/tab_2004.pkl')
P('\nVARIANTI CONTATE (selezione x target, esclusi i quinti intermedi e le righe di confronto):', NV)
open(f'{OUT}/f1_03.log', 'w').write('\n'.join(LOG))
