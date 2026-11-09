# Storico 2000-2011, fase 5: liste di ticker per domani (nessuna chiamata a EODHD).
import os, sys, pickle, pandas as pd
ML = os.path.dirname(os.path.abspath(__file__)); BW = os.path.dirname(ML); sys.path.insert(0, BW)
from world_common import symbols
SO = f'{ML}/sopravv'
s = symbols('US'); s['base'] = s.Code.str.replace(r'_old\d*', '', regex=True)
b11 = set(pd.read_pickle(f'{BW}/eod/bulk_US.pkl').code)
D = pd.read_pickle(f'{SO}/buco_usa_dettaglio.pkl'); k = D[~D.escl]
n = k.groupby('code').agg(n=('date', 'size'), A=('A', 'max'), B=('B', 'max'), C=('C', 'max'))
# C: ancora quotati dopo il 2011, liquidi in >=3 istantanee 2000-2010 -> bilanci + prezzi
C = n[(n.n >= 3) & n.C & ~n.A & ~n.B].index
open(f'{SO}/domani_usa_C_bilanci.txt', 'w').write('\n'.join(f'{c}.US' for c in C))
# B: usciti prima di meta' 2011, liquidi in >=1 istantanea -> solo prezzi (EODHD non ha i bilanci)
B = n[(n.n >= 1) & n.B & ~n.A].index
dl = s[s.delisted == 1]
plain = set(dl[~dl.Code.str.contains('_old')].Code)
olds = dl[dl.Code.str.contains('_old')].groupby('base').Code.apply(list)
out, amb = [], 0
for c in B:
    if c in plain and c not in b11: out.append(f'{c}.US')
    if c in olds.index:
        out += [f'{x}.US' for x in olds[c]]; amb += 1
out = sorted(set(out))
open(f'{SO}/domani_usa_B_prezzi.txt', 'w').write('\n'.join(out))
# ex-USA nel panel con soli campi "vecchi" (fund.pkl): da riscaricare con i campi nuovi
f2 = pickle.load(open(f'{BW}/fund/fund2.pkl', 'rb')); p = pd.read_pickle(f'{BW}/res/panel2.pkl')
R = sorted(set(p.t) - set(f2))
open(f'{SO}/domani_exusa_bilanci_completi.txt', 'w').write('\n'.join(R))
print('C bilanci', len(C), '| B prezzi: codici', len(B), 'ticker da chiamare', len(out), 'di cui con varianti _old', amb, '| ex-USA da riscaricare', len(R))
