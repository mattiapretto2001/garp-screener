# Controllo previsto dalle regole congelate e non fatto: soglie corrette per l'inflazione (3 M$ e 300 M$ in dollari 2026)
import sys, pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
ML='${RICERCA_BASE}/backtest_world/ml'; O=f'{ML}/storico5'
sys.path.insert(0, ML)
from sA_common import build
CPI={1999:166.6,2000:172.2,2001:177.1,2002:179.9,2003:184.0,2004:188.9,2005:195.3,2006:201.6,2007:207.3,2008:215.3,2009:214.5,2010:218.1,2011:224.9}
P=pd.read_pickle(f'{O}/pannello_prezzi_us_v2.pkl'); P=P[P.date<='2011-09-30'].reset_index(drop=True)
k=330.0/P.date.dt.year.map(CPI)
Pi=P.copy(); Pi['dv63']=P.dv63*k; Pi['cap']=P.cap*k
ew=lambda X: X.groupby('date').f12.mean().mean()
for lab,PP in [('nominale',P),('reale (dollari 2026)',Pi)]:
    U=build(PP); H=U[U.storico]
    print(f'{lab:22s} titoli/data {len(H)/H.date.nunique():.0f} crolli {H.L50.mean():.4f} ew {ew(H):.4f} rapporti '+
          ' '.join(f'{X[X.p52<0.4].L50.mean()/X.L50.mean():.2f}' for X in [H[H.blocco==b] for b in ['2000-03','2004-07','2008-11']])+
          ' | guardia esc/amm '+' '.join(f'{X[X.p52<0.4].L50.mean():.3f}/{X[X.p52>=0.4].L50.mean():.3f}' for X in [H[H.blocco==b] for b in ['2000-03','2004-07','2008-11']]))
