# Prova C (08/11/2026), fase 3: tutte le varianti, 300 portafogli a caso per variante (stessi semi per tutte le regole).
# CRITERIO PER "LA REGOLA CHE REGGE MEGLIO", FISSATO PRIMA DI GUARDARE I RISULTATI:
#   riferimento = L/none (uscita dalla lista, lasciar correre con il solo taglio sopra il 10%). Una regola "regge" se:
#   (1) il rendimento mediano del 50/50 (ribilanciato ogni gennaio) e' sopra il riferimento sia nel 2000-2011 (proxy) sia nel
#       2012-2026 (liste vere);
#   (2) la meta' moltiplicatori batte il riferimento (mediana) in almeno 3 dei 4 sotto-periodi 2000-05, 2006-11, 2012-17, 2018-26;
#   (3) la perdita massima mediana del 50/50 non e' peggiore del riferimento di oltre 5 punti in nessuno dei due periodi.
#   Fra quelle che reggono vince la media piu' alta del vantaggio mediano del 50/50 nei due periodi. Controlli: proxy prudente,
#   proxy 2012-2025 (ponte), liste vere solo USA, tasse.
import os, sys, pickle, time, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import c02_sim as S
from multiprocessing import Pool
NSEED = 300
SUB = {'P1': [('2000-05', '2000-01-01', '2006-01-01'), ('2006-11', '2006-01-01', '2099-01-01')],
       'P1p': [('2000-05', '2000-01-01', '2006-01-01'), ('2006-11', '2006-01-01', '2099-01-01')],
       'P2': [('2012-17', '2012-01-01', '2018-01-01'), ('2018-26', '2018-01-01', '2099-01-01')],
       'P2us': [('2012-17', '2012-01-01', '2018-01-01'), ('2018-26', '2018-01-01', '2099-01-01')],
       'P3': [('2012-17', '2012-01-01', '2018-01-01'), ('2018-25', '2018-01-01', '2099-01-01')]}
_D = {}


def D_of(key):
    if key not in _D: _D[key] = S.load(key)
    return _D[key]


def maxdd(v):
    v = np.asarray(v, float); return float((v / np.maximum.accumulate(v) - 1).min())


def metrics(key, r, D, tax):
    cal = D['cal']; days = r['days']; V = r['vals']
    dts = cal[days]; Sv = V[:, 0]; Wv = V[:, 1]; Cs = V[:, 2]
    yrs = (dts[-1] - dts[0]).days / 365.25
    m = {}
    m['cagr_s'] = (Sv[-1] / Sv[0]) ** (1 / yrs) - 1
    m['cagr_w'] = (Wv[-1] / Wv[0]) ** (1 / yrs) - 1
    comb = Sv + Wv
    m['cagr_c'] = (comb[-1] / comb[0]) ** (1 / yrs) - 1
    # 50/50 ribilanciato a ogni primo controllo di gennaio
    rs = Sv[1:] / Sv[:-1] - 1; rw = Wv[1:] / Wv[:-1] - 1
    a = b = 50.0; cr = [100.0]
    for i in range(len(rs)):
        if dts[i].month == 1 and i > 0: t = a + b; a = b = t / 2
        a *= 1 + rs[i]; b *= 1 + rw[i]; cr.append(a + b)
    cr = np.array(cr)
    m['cagr_cr'] = (cr[-1] / cr[0]) ** (1 / yrs) - 1
    m['dd_s'] = maxdd(Sv); m['dd_w'] = maxdd(Wv); m['dd_c'] = maxdd(comb); m['dd_cr'] = maxdd(cr)
    for nm, a0, b0 in SUB[key]:
        i0 = np.searchsorted(dts.values, np.datetime64(a0)); i1 = min(np.searchsorted(dts.values, np.datetime64(b0)), len(dts) - 1)
        y = (dts[i1] - dts[i0]).days / 365.25
        m[f'cagr_s|{nm}'] = (Sv[i1] / Sv[i0]) ** (1 / y) - 1
        m[f'cagr_w|{nm}'] = (Wv[i1] / Wv[i0]) ** (1 / y) - 1
        m[f'cagr_cr|{nm}'] = (cr[i1] / cr[i0]) ** (1 / y) - 1
    m['cash'] = float(np.mean(Cs[1:] / np.maximum(Sv[1:], 1e-9)))
    m['trades_y'] = r['ntrade'] / yrs
    R = r['recs']
    inv = np.array([x[3] for x in R]); proc = np.array([x[4] for x in R]); mult = proc / inv
    pl = proc - inv
    pk = np.array([x[6] for x in R]); hold = np.array([(cal[x[2]] - cal[x[1]]).days / 365.25 for x in R])
    why = np.array([x[5] for x in R])
    m['npos'] = len(R)
    tot = pl.sum(); k = max(1, int(np.ceil(0.10 * len(pl))))
    top = np.sort(pl)[::-1][:k].sum()
    m['top10'] = top / tot if tot > 0 else np.nan
    m['top10_pos'] = top / pl[pl > 0].sum() if (pl > 0).any() else np.nan
    m['tot_pl_pos'] = tot > 0
    if tax:
        m['cagr_s_tax'] = (r['S_net'] / 50) ** (1 / yrs) - 1
        m['cagr_w_tax'] = (r['W_net'] / 50) ** (1 / yrs) - 1
        m['cagr_c_tax'] = ((r['S_net'] + r['W_net']) / 100) ** (1 / yrs) - 1
    # anno per anno (meta' moltiplicatori), dal primo controllo dell'anno al primo dell'anno dopo
    ann = {}
    for y in sorted(set(dts.year)):
        ii = np.where(dts.year == y)[0]
        j1 = ii[-1] + 1 if ii[-1] + 1 < len(dts) else ii[-1]
        ann[y] = Sv[j1] / Sv[ii[0]] - 1
    m['ann'] = ann
    pos = np.rec.fromarrays([mult.astype(np.float32), pk.astype(np.float32), hold.astype(np.float32), why,
                             np.array([x[0] for x in R], np.int32), np.array([x[1] for x in R], np.int32), pl.astype(np.float32)],
                            names='mult,peak,hold,why,j,d0,pl')
    return m, pos


def job(args):
    key, base, over, tax = args
    D = D_of(key)
    rows, P = [], []
    for s in range(NSEED):
        r = S.run(D, base, over, s, tax)
        m, pos = metrics(key, r, D, tax)
        m.update(key=key, base=base, over=over, tax=tax, seed=s); rows.append(m); P.append(pos)
    return (key, base, over, tax), rows, np.concatenate(P)


if __name__ == '__main__':
    t0 = time.time()
    jobs = [(k, b, o, False) for k in ['P1', 'P2', 'P3', 'P1p', 'P2us'] for b, o in S.VARIANTS]
    jobs += [(k, b, o, True) for k in ['P1', 'P2'] for b, o in S.VARIANTS]
    ROWS, POS = [], {}
    with Pool(4) as pool:
        for i, (kk, rows, P) in enumerate(pool.imap_unordered(job, jobs)):
            ROWS += rows
            if not kk[3]: POS[kk] = P
            if i % 10 == 0: print(i, 'di', len(jobs), round(time.time() - t0), 's', flush=True)
    T = pd.DataFrame(ROWS)
    T.to_pickle(f'{HERE}/dati/runs.pkl')
    pickle.dump(POS, open(f'{HERE}/dati/posizioni.pkl', 'wb'), protocol=4)
    print('fatto', T.shape, round(time.time() - t0), 's')
