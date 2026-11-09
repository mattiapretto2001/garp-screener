# scr_04c (prova a posteriori, dichiarata): Q3 con le esclusioni GARP ma riammettendo pagamenti e dati finanziari
# (industrie "Credit Services" e "Financial Data & Stock Exchanges"), dove stanno Mastercard, Visa, S&P Global.
import pandas as pd
from scr_common import *
EXC = F.industry.fillna('').str.strip().isin(['Credit Services', 'Financial Data & Stock Exchanges'])
R = []
for nm, m in [('Q3 esclusioni GARP', Q3_G), ('Q3 esclusioni GARP + pagamenti/dati', Q3_G | (Q3 & EXC)), ('solo i riammessi', Q3 & EXC & ~UNI)]:
    o, _ = ev(nm, m, ALL, 'eccezione'); R += o
T = pd.DataFrame(R); T.to_csv(f'{BASE}/res/scr_04c.csv', index=False)
pd.set_option('display.width', 250); print(fmt(T).to_string())
print(F[Q3 & EXC & ~UNI & (F.date == REB[-1])][['t', 'name', 'industry']].to_string())
