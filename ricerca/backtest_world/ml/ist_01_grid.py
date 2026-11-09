# ist_01: griglia liste x N x regole x periodi, lordo e netto di tasse. Salva tabella e serie trimestrali.
import sys, os, pickle, itertools, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from ist_common import *
print('controllo r_eur fuori pannello vs pannello:', CHK)
RULES = [('a', dict(freq=1)), ('a', dict(freq=2)), ('a', dict(freq=4)), ('a2', dict(freq=1))]
RULES += [('b', dict(K=K, M=M, freq=f)) for K in (10, 15, 20) for M in (30, 40, 60) for f in (1, 2)]
RULES += [('c', dict(X=X)) for X in (2, 3, 5, None)]
# variante aggiunta dopo la diagnosi ist_02 (i titoli perdono il vantaggio appena escono dalla lista): grazia 1 trimestre
RULES += [('b', dict(K=K, M=M, freq=1, grace=1)) for K in (10, 15, 20) for M in (30, 60, None)]
rows, SER = [], {}
t0 = time.time()
for p in PER:
    ds = pdates(p); yrs = (NXT[ds[-1]] - ds[0]).days / 365.25
    for tax in (True, False):
        v = sim_vwce(ds, tax=tax)
        rows.append(dict(lista='VWCE', N=0, regola='VWCE', K=None, M=None, X=None, freq=None, grazia=None, periodo=p, tasse=tax, irr=v['irr'], W=v['W'],
                         W_pre=v['W_pre'], versato=v['contrib'], twr=ann_twr(v['twr']), fees=v['fees'], spread=0, taxpaid=np.nan, ordini_anno=np.nan,
                         rotazione=np.nan, nhold=1))
        SER[('VWCE', 0, 'VWCE', None, None, None, None, None, p, tax)] = v['twr']
        for lk, N, (rule, kw) in itertools.product(CFG, (8, 10, 12, 15, 20), RULES):
            r = sim(CFG[lk](N), rule, ds, tax=tax, **kw)
            key = (lk, N, rule, kw.get('K'), kw.get('M'), kw.get('X'), kw.get('freq', 1), kw.get('grace', 2), p, tax)
            SER[key] = r['twr']
            avgW = (r['W_pre'] + 9500) / 2
            rows.append(dict(lista=lk, N=N, regola=rule, K=kw.get('K'), M=kw.get('M'), X=kw.get('X'), freq=kw.get('freq', 1), grazia=kw.get('grace', 2), periodo=p,
                             tasse=tax, irr=r['irr'], W=r['W'], W_pre=r['W_pre'], versato=r['contrib'], twr=ann_twr(r['twr']), fees=r['fees'],
                             spread=r['spread'], taxpaid=r['taxpaid'], ordini_anno=r['orders'] / yrs, rotazione=r['traded'] / 2 / yrs / r['vmean'], costi_pct=(r['fees'] + r['spread']) / yrs / r['vmean'], tasse_pct=r['taxpaid'] / yrs / r['vmean'],
                             nhold=r['nhold']))
    print(p, 'fatto', round(time.time() - t0), 's', flush=True)
T = pd.DataFrame(rows)
T.to_csv(f'{OUTD}/ist_01_griglia.csv', index=False)
pickle.dump(SER, open(f'{OUTD}/ist_01_serie.pkl', 'wb'))
print(len(T), 'righe')
