# F1 passo 4 (controlli aggiunti DOPO aver visto f1_03, dichiarati come tali nel rapporto):
#  a) inv=0 contro inv=1 solo dove inv e' definito (il confronto con l'universo in f1_03 e' falsato dalle societa' in perdita);
#  b) punteggio S senza la dimensione (per capire se tutto viene dalle piccole);
#  c) S dentro le sole societa' >= 2 miliardi $ (la taglia delle nostre liste).
import pandas as pd, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f1_common import *
LOG = []
def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.append(s)
cols = ['t', 'date', 'reg', 'reg_rob', 'per3', 'excl_sector', 'fcfy', 'pb', 'ev', 'mcap', 'mcap_usd', 'fx_rep', 'equity', 'ni_ttm', 'ta',
        'asset_g', 'ebitda_ttm', 'mom3', 'mom6', 'x3', 'top5_reg', 'bot20_reg', 'crash50']
F = pd.read_pickle(f'{ML}/features_v3.pkl')[cols].merge(pd.read_pickle(f'{OUT}/pr_2012.pkl'), on=['t', 'date'], how='left')
F = add_vars(F, 'reg').reset_index(drop=True)
TG = ['x3', 'top5_reg', 'bot20_reg', 'crash50']; STEP = {'x3': 12, 'top5_reg': 4, 'bot20_reg': 4, 'crash50': 4}

def cmp(a, b, lab, pool=None):
    pool = pd.Series(True, index=F.index) if pool is None else pool
    out = {'confronto': lab}
    for tg in TG:
        X = F[pool & F[tg].notna()]
        ra = X[a[X.index]].groupby('date')[tg].mean(); rb = X[b[X.index]].groupby('date')[tg].mean()
        out[tg + '_A'] = X.loc[a[X.index], tg].mean(); out[tg + '_B'] = X.loc[b[X.index], tg].mean()
        out[tg + '_t'] = nov_t(ra - rb, STEP[tg])[0]
    return out

R = [cmp(F.inv == 0, F.inv == 1, 'inv=0 (A) contro inv=1 (B), solo definiti')]
F['S_nosize'] = F[[f'k_{c}' for c in COMP if c != 'size']].mean(axis=1)
q = F.groupby(['date', 'reg']).S_nosize.rank(pct=True, method='first') > 0.8
R.append(cmp(q, pd.Series(True, index=F.index), 'S senza dimensione: quinto alto (A) contro universo (B)'))
big = F.mcap_usd >= 2e9
F['S_big'] = np.nan
F.loc[big, 'S_big'] = F[big].groupby(['date', 'reg']).S.rank(pct=True, method='first')
R.append(cmp(F.S_big > 0.8, big, 'solo >=2 Mld$: quinto alto di S (A) contro tutte >=2 Mld$ (B)', pool=big))
T = pd.DataFrame(R); P(T.round(4).to_string(index=False))
# rapporto x3 / crolli per quinto di S (qualita' della scommessa)
g = F.groupby('qS')[['x3', 'crash50', 'bot20_reg', 'top5_reg']].mean()
g['x3_per_crollo'] = g.x3 / g.crash50; g['top5_per_disastro'] = g.top5_reg / g.bot20_reg
P('\nper quinto di S:'); P(g.round(4).to_string())
open(f'{OUT}/f1_04.log', 'w').write('\n'.join(LOG))
