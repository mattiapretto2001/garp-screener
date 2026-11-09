# Quante righe del sostituto toglie il controllo q1 (prezzo corretto al tetto di 1.000.000 nei 12 mesi DOPO la data: guarda avanti)?
import sys, os, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
ML = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ML); sys.path.insert(0, os.path.dirname(ML)); sys.path.insert(0, f'{ML}/regoleC')
import c01_prep as C
from s5_common import OUT as S5
P = pd.read_pickle(f'{S5}/pannello_prezzi_us_v2.pkl')
Cc = pd.read_pickle(f'{S5}/volumi_corretti_A.pkl').set_index(['t', 'date'])
j = Cc.reindex(pd.MultiIndex.from_frame(P[['t', 'date']]))
Pv = P.copy(); hv = j.dv63_v.notna().values
Pv.loc[hv, 'dv63'] = j.dv63_v.values[hv]; Pv.loc[hv, 'px'] = j.px_v.values[hv]
U1 = C.build_univ(Pv, '2011-09-30')
Pv2 = Pv.copy(); Pv2['a_tetto'] = False
U2 = C.build_univ(Pv2, '2011-09-30')
L1 = C.proxy_lists(U1); L2 = C.proxy_lists(U2)
add = []
for d in L2:
    extra = set(L2[d]) - set(L1.get(d, []))
    for t in extra: add.append((d, t))
A = pd.DataFrame(add, columns=['date', 't'])
print('righe di lista 2000-11 col controllo:', sum(len(v) for v in L1.values()), '| senza:', sum(len(v) for v in L2.values()), '| in piu:', len(A))
print(A.groupby('t').date.agg(['min', 'max', 'size']).to_string())
