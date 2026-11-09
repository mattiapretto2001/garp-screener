# Verifica avversariale Prova C: le conclusioni reggono se cambio costi, data di partenza, crolli finti, regola dei fallimenti,
# titoli non comprabili (Taiwan, Corea) e i nomi migliori? Stessi semi 0-299 del rapporto. Nessuna chiamata EODHD.
import sys, os, time, pickle, copy, numpy as np, pandas as pd
ML = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, f'{ML}/regoleC')
import c02_sim as S, c03_run as R
from multiprocessing import Pool
OUT = f'{ML}/avv_C_out'
_B = {}

def base(key):
    if key not in _B: _B[key] = S.load(key)
    return _B[key]

def shift(D, start):
    D = dict(D); i0 = int(np.searchsorted(D['cal'][D['ms']].values, np.datetime64(start)))
    for f in ['ms', 'cur', 'sets', 'newq']: D[f] = D[f][i0:] if f == 'ms' else D[f][i0:]
    return D

def drop_names(D, bad):
    D = dict(D); bad = set(bad)
    D['cur'] = [np.array([j for j in x if j not in bad], int) for x in D['cur']]
    D['sets'] = [set(x) - bad for x in D['sets']]
    return D

def fix_crolli(D):
    E = pd.read_pickle(f'{OUT}/crolli_P1.pkl'); E = E[E.sospetto].sort_values(['j', 'k'])
    D = dict(D); M = D['M'].copy(); last = D['last'].copy(); ended = D['ended'].copy(); bk = D['bk'].copy()
    for j, g in E.groupby('j'):
        for _, e in g.iterrows():
            k = int(e.k)
            if k > last[j]: break
            if e.split_near:
                M[j, k:last[j] + 1] /= e.rapporto          # frazionamento non corretto: tolgo il salto
            else:                                         # innesto o codice mescolato: la serie finisce il giorno prima, incasso
                M[j, k:] = np.nan; last[j] = k - 1; ended[j] = True; bk[j] = False; break
    D.update(M=M, last=last, ended=ended, bk=bk); return D

def bk_rule(D, mode):
    D = dict(D); bk = D['bk'].copy(); M = D['M']
    for j in np.where(D['ended'])[0]:
        if mode == 'mai': bk[j] = False
        else:
            l = D['last'][j]; h = np.nanmax(M[j, max(0, l - 261):l + 1])
            bk[j] = bool(M[j, l] < 0.5 * h)
    D['bk'] = bk; return D

def make(key, mod):
    D = base(key)
    if mod == 'base': return D
    if mod.startswith('da'): return shift(D, mod[2:])
    if mod == 'crolli': return fix_crolli(D)
    if mod.startswith('fall'): return bk_rule(D, mod[4:])
    if mod == 'noasia':
        return drop_names(D, [j for j, t in enumerate(D['tick']) if t.endswith('.TW') or t.endswith('.KO')])
    if mod == 'notop':
        top = pickle.load(open(f'{OUT}/top_P2.pkl', 'rb')); return drop_names(D, top)
    if mod.startswith('costo'): return D
    raise ValueError(mod)

def job(args):
    key, mod, b, o = args
    S.COST = float(mod[5:]) if mod.startswith('costo') else 0.005
    D = make(key, mod); rows = []
    for s in range(300):
        r = S.run(D, b, o, s, False); m, _ = R.metrics(key, r, D, False); m.pop('ann')
        m.update(key=key, mod=mod, base=b, over=o, seed=s); rows.append(m)
    return rows

if __name__ == '__main__':
    # i 10 nomi che contano di piu' nel 2012-26 (somma dei guadagni nei 300 portafogli), con lista e con 3 anni
    POS = pickle.load(open(f'{ML}/regoleC/dati/posizioni.pkl', 'rb'))
    top = set()
    for rule in [('L', 'none'), ('T3', 'none')]:
        P = POS[('P2',) + rule + (False,)].view(np.recarray)
        s = pd.Series(P.pl).groupby(P.j).sum().sort_values(ascending=False); top |= set(s.index[:10].tolist())
    tick = pickle.load(open(f'{ML}/regoleC/dati/P2.pkl', 'rb'))['tick']
    print('nomi tolti:', sorted(tick[j] for j in top), flush=True)
    pickle.dump(sorted(top), open(f'{OUT}/top_P2.pkl', 'wb')); del POS
    V5 = [('L', 'none'), ('L', 'TR3'), ('L', 'AD30'), ('L', 'S30'), ('T2', 'none'), ('T3', 'none')]
    jobs = []
    for key in ['P1', 'P2']:
        jobs += [(key, 'costo0.01', b, o) for b, o in V5]
    jobs += [('P1', m, b, o) for m in ['da2001-01-01', 'da2003-01-01', 'crolli', 'fallmai', 'fall50'] for b, o in V5]
    jobs += [('P2', m, b, o) for m in ['da2014-01-01', 'da2016-01-01', 'noasia', 'notop'] for b, o in V5]
    t0 = time.time()
    with Pool(4) as P:
        T = pd.DataFrame([x for rows in P.imap_unordered(job, jobs) for x in rows])
    T.to_pickle(f'{OUT}/runs_robusto.pkl'); print('fatto', round(time.time() - t0), 's', flush=True)
