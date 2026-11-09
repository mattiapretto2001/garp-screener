# avv_reg_07: i target sono ranghi in EUR dentro regioni multi-valuta (Europa, Asia, Altri): le variabili che differiscono per borsa
# (es. profondita' dell'archivio EODHD) potrebbero catturare effetti paese/valuta. Rifaccio ranghi di variabili e target per data x borsa.
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fv3, regcommon as rc
warnings.filterwarnings('ignore')
M = rc.load(); F = fv3.load(cols=['ex', 'fwd12_loc'])
M['ex'] = F.ex.astype(str).values; M['fwd12_loc'] = F.fwd12_loc.values
M = M[M.fwd12_eur.notna()].reset_index(drop=True)
n = M.groupby(['date', 'ex']).t.transform('count'); M = M[n >= 40].copy()
G = rc.GLOBAL; ZG = ['z_' + c for c in G]
M[ZG] = rc.rank_z(M, ZG, ['date', 'ex']).values
for tgt, nm in [('fwd12_eur', 'EUR'), ('fwd12_loc', 'valuta locale')]:
    S = M[M[tgt].notna()].copy()
    S['y_rk'] = rc.rank_z(S.assign(f=S[tgt]), ['f'], ['date', 'ex'])['f']
    gq = S.groupby(['date', 'ex'])[tgt]; rk = (gq.rank() - 0.5) / gq.transform('count')
    S['bot20'] = (rk <= 0.2) * 100.; S['top5'] = (rk >= 0.95) * 100.
    for sub, msk in [('tutte', np.ones(len(S), bool)), ('fuori USA', (S.reg != 'USA').values)]:
        out = []
        for y in ['y_rk', 'top5', 'bot20']:
            C = rc.fm(S.loc[msk, ['date'] + ZG + [y]], ZG, y)
            out.append(y + ': ' + ', '.join('%s %.1f' % (k, fv3.nw_t(C['z_' + k])) for k in ['hist_y', 'fcf_m', 'dsh1', 'hi52', 'cash_mcap', 'vol1y']))
        print('ranghi per borsa, target %-13s %-9s | %s' % (nm, sub, ' || '.join(out)))
