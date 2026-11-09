# ist_03: ogni regola contro la regola di oggi (a, trimestrale) per lista e N: differenza di rendimento annuo (IRR) lordo e netto,
# t di Newey-West sulla differenza trimestrale (rendimenti a ponderazione temporale, trimestri che non si sovrappongono).
import sys, os, pickle
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
from ist_common import nwt, OUTD
T = pd.read_csv(f'{OUTD}/ist_01_griglia.csv'); SER = pickle.load(open(f'{OUTD}/ist_01_serie.pkl', 'rb'))
T = T[T.lista != 'VWCE'].copy()
def cfg(r):
    if r.regola == 'a': return f"a f{int(r.freq)}"
    if r.regola == 'a2': return 'a2'
    if r.regola == 'b': return f"b K{int(r.K)} M{'-' if pd.isna(r.M) else int(r.M)} f{int(r.freq)} g{int(r.grazia)}"
    return f"c X{'-' if pd.isna(r.X) else int(r.X)}"
T['cfg'] = T.apply(cfg, axis=1)
def key(r):
    nn = lambda v: None if pd.isna(v) else (int(v) if not isinstance(v, str) else v)
    return (r.lista, int(r.N), r.regola, nn(r.K), nn(r.M), nn(r.X), int(r.freq), int(r.grazia), r.periodo, bool(r.tasse))
T['key'] = T.apply(key, axis=1)
base = T[T.cfg == 'a f1'].set_index(['lista', 'N', 'periodo', 'tasse'])
rows = []
for (lk, c, p, tx), g in T.groupby(['lista', 'cfg', 'periodo', 'tasse']):
    d_irr = [r.irr - base.loc[(lk, r.N, p, tx)].irr for r in g.itertuples()]
    d_ser = sum(SER[k] - SER[base.loc[(lk, n, p, tx)].key] for k, n in zip(g.key, g.N)) / len(g)
    rows.append(dict(lista=lk, cfg=c, periodo=p, tasse=tx, irr=g.irr.mean(), d_irr=np.mean(d_irr), d_min=np.min(d_irr), d_max=np.max(d_irr),
                     n_meglio=int(np.sum(np.array(d_irr) > 0)), t_nw=nwt(d_ser), ordini=g.ordini_anno.mean(), rot=g.rotazione.mean(),
                     costi=g.costi_pct.mean(), tasse_pct=g.tasse_pct.mean(), nhold=g.nhold.mean()))
C = pd.DataFrame(rows); C.to_csv(f'{OUTD}/ist_03_confronto.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 2000)
for p in ['2018-26', '2012-17']:
    X = C[(C.periodo == p) & C.tasse].copy()
    for c in ['irr', 'd_irr', 'd_min', 'd_max', 'costi', 'tasse_pct', 'rot']: X[c] = (X[c] * 100).round(1)
    print('=====', p, 'netto')
    print(X.drop(columns=['periodo', 'tasse']).round(2).to_string(index=False))
