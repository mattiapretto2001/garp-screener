# F1 passo 2: le liste dello screener (regole congelate in scr_common.py), esportate come colonne (t, date).
# GARP core = CORE; Crescita = CR; Qualita' = Q3; Radar = RADA (Radar A). Nessuna regola ritoccata.
import sys, os
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML); sys.path.insert(0, BW)
import scr_common as S
L = S.F[['t', 'date']].copy()
for k in ['CORE', 'CR', 'Q3', 'RADA', 'A']: L[k] = getattr(S, k).values
L.to_pickle(f'{ML}/f1_out/liste.pkl')
print(L.groupby('date')[['CORE', 'CR', 'Q3', 'RADA', 'A']].sum().mean().round(1))
