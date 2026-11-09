# temi_05: quali industrie la regola avrebbe segnalato nel passato (senza forzare nulla) e come sono andate dopo
from temi_common import *
V = pd.read_pickle(f'{OUT}/ind_flags2.pkl')
V['pctB'] = V.groupby('date').scoreB.rank(pct=True); V['pctM'] = V.groupby('date').mom_med.rank(pct=True)
V['yr'] = V.date.dt.year
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 400)
# 1) per anno: industrie segnalate da B almeno 2 trimestri su 4, con esito medio a 12 mesi (eccesso vs regione, pp)
rows = []
for y, g in V.groupby('yr'):
    for r in ['B', 'BM']:
        c = g[g[r]].groupby('ind').agg(q=('date', 'size'), y=('y_xs', 'mean'), yrel=('y_xs', lambda s: np.nan))
        c = c[c.q >= (2 if r == 'B' else 1)].sort_values('q', ascending=False)
        rows.append({'anno': y, 'regola': r, 'n': len(c),
                     'industrie': '; '.join(f"{i} ({q}t, {'n.d.' if not np.isfinite(v) else f'{100*v:+.0f}'})" for i, q, v in zip(c.index, c.q, c.y))})
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/storia_per_anno.csv', index=False)
for _, r in T[T.regola == 'B'].iterrows(): print(r.anno, r.regola, r.n, '|', r.industrie)
print()
for _, r in T[T.regola == 'BM'].iterrows(): print(r.anno, r.regola, r.n, '|', r.industrie)
# 2) casi di controllo, scelti PRIMA di guardare (temi famosi): percentile del punteggio B e del momentum, segnali, esito
CASI = {'Semiconduttori (IA 2023)': ['Semiconductors', 'Semiconductor Equipment & Materials'],
        'Hardware/server IA': ['Computer Hardware', 'Electronic Components', 'Communication Equipment'],
        'GLP-1 / obesita\'': ['Drug Manufacturers - General'],
        'Rete elettrica / energia 2024': ['Electrical Equipment & Parts', 'Utilities - Independent Power Producers', 'Utilities - Regulated Electric',
                                          'Engineering & Construction', 'Specialty Industrial Machinery'],
        'Uranio / nucleare': ['Uranium'], 'Solare': ['Solar'], 'Difesa': ['Aerospace & Defense'], 'Oro': ['Gold'], 'Rame': ['Copper'],
        'Covid digitale 2020': ['Internet Retail', 'Software - Application', 'Software - Infrastructure'],
        'Riapertura 2021': ['Airlines', 'Travel Services', 'Lodging'], 'Petrolio 2021-22': ['Oil & Gas E&P', 'Oil & Gas Integrated'],
        'Trasporto marittimo 2021': ['Marine Shipping']}
out = []
for tema, inds in CASI.items():
    for ind in inds:
        g = V[V.ind == ind].sort_values('date')
        if g.empty: print('manca', ind); continue
        for _, r in g[g.date >= '2019-06-30'].iterrows():
            out.append({'tema': tema, 'ind': ind, 'date': r.date.date(), 'n': int(r.n), 'pctB': r.pctB, 'pctM': r.pctM, 'B': r.B, 'MOM': r.MOM, 'BM': r.BM, 'A': r.A,
                        'accel': r.accel_agg, 'qa': r.qa, 'd_pos2': r.d_pos2, 'pos': r.pos, 'd_marg': r.d_marg, 'y_xs': r.y_xs})
O = pd.DataFrame(out); O.to_csv(f'{OUT}/storia_casi.csv', index=False)
def flagstr(g):
    return ' '.join(f"{str(d)[2:7]}:{'B' if b else ''}{'M' if m else ''}{'' if (b or m) else '.'}" for d, b, m in zip(g.date, g.B, g.MOM))
for (tema, ind), g in O.groupby(['tema', 'ind'], sort=False):
    print(f'{tema} | {ind} | {flagstr(g)}')
# 3) quando una famosa industria e' stata segnalata la prima volta (da 2019) e come e' andata
