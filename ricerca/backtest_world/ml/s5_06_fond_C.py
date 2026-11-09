# Storico 2000-2011, punto 5.2b: bilanci delle americane "classe C" (liquide nel 2000-2011, ancora quotate dopo meta' 2011,
# assenti dai nostri dati). Servono alla prova della diluizione e, domani, alla prova dei punteggi sul 2006-2011.
# Formato compatto come fund2 (world_11_fund2.extract). 10 crediti l'una; tetto passato come argomento (contatore assoluto).
# uso: python3 s5_06_fond_C.py [tetto]   (default 95.900)
import sys, os, pickle, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from s5_common import get, usage, OUT, BW
sys.path.insert(0, BW)
import world_11_fund2 as W
STOP = int(sys.argv[1]) if len(sys.argv) > 1 else 95900
D = pd.read_pickle(f'{OUT}/pannello_prezzi_us.pkl')
D['anno'] = (D.date + pd.Timedelta(days=1)).dt.year
b = (D.px >= 3) & (D.dv63 >= 3e6) & (D.n1y >= 200) & D.p52.notna() & (D.anno <= 2011)
C = D[b & (D.src == 'D') & ~D.uscita_pre2011]
order = C.groupby('t').size().sort_values(ascending=False).index.tolist()
fn = f'{OUT}/fond_C.pkl'
F = pickle.load(open(fn, 'rb')) if os.path.exists(fn) else {}
todo = [t for t in order if f'{t}.US' not in F]
print('classe C', len(order), 'da scaricare', len(todo), 'contatore', usage(), flush=True)


def one(t):
    j = get(f'fundamentals/{t}.US')
    if not isinstance(j, dict) or not j: return f'{t}.US', None
    try: return f'{t}.US', W.extract(j)
    except Exception as e: return f'{t}.US', {'err': str(e)}


for i in range(0, len(todo), 100):
    u = usage()
    if u is None or u > STOP - 1000: print('STOP contatore', u, flush=True); break
    with ThreadPoolExecutor(8) as P:
        for t, d in P.map(one, todo[i:i + 100]): F[t] = d
    pickle.dump(F, open(fn, 'wb'))
    print(i + 100, 'fatti; contatore', usage(), flush=True)
ok = sum(1 for v in F.values() if isinstance(v, dict) and v.get('inc_y') is not None and len(v.get('inc_y')))
print('fine; con bilanci', ok, 'su', len(F), 'contatore', usage())
