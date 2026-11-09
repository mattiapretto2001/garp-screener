# Verifica avversariale Prova C: (1) il codice di oggi rifà runs.pkl? (2) il criterio fissato prima con 300 semi NUOVI (1000-1299).
import sys, os, time, pickle, numpy as np, pandas as pd
ML = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, f'{ML}/regoleC')
import c02_sim as S, c03_run as R
from multiprocessing import Pool
OUT = f'{ML}/avv_C_out'
SEEDS = range(1000, 1300)

def job(args):
    key, b, o = args
    D = R.D_of(key); rows = []
    for s in SEEDS:
        r = S.run(D, b, o, s, False)
        m, _ = R.metrics(key, r, D, False); m.pop('ann')
        m.update(key=key, base=b, over=o, seed=s); rows.append(m)
    return rows

if __name__ == '__main__':
    # (1) riproduzione esatta di alcuni portafogli
    T0 = pd.read_pickle(f'{ML}/regoleC/dati/runs.pkl'); T0 = T0[~T0.tax]
    for key in ['P1', 'P2']:
        D = R.D_of(key)
        for b, o in [('L', 'none'), ('L', 'TR3'), ('T3', 'none')]:
            for s in [0, 7, 123]:
                m, _ = R.metrics(key, S.run(D, b, o, s, False), D, False)
                ref = T0[(T0.key == key) & (T0.base == b) & (T0.over == o) & (T0.seed == s)].iloc[0]
                print('ripro', key, b, o, s, round(m['cagr_cr'], 6), round(ref.cagr_cr, 6), 'uguale' if abs(m['cagr_cr'] - ref.cagr_cr) < 1e-9 else 'DIVERSO', flush=True)
    t0 = time.time()
    jobs = [(k, b, o) for k in ['P1', 'P2'] for b, o in S.VARIANTS]
    with Pool(4) as P:
        T = pd.DataFrame([x for rows in P.imap_unordered(job, jobs) for x in rows])
    T.to_pickle(f'{OUT}/runs_semi_nuovi.pkl'); print('fatto', round(time.time() - t0), 's')
    SUBN = {'P1': ['2000-05', '2006-11'], 'P2': ['2012-17', '2018-26']}
    def summ(X):
        out = {}
        for (b, o), g in X.groupby(['base', 'over']):
            r = dict(cr=g.cagr_cr.median(), dd=g.dd_cr.median())
            for s in SUBN[g.key.iloc[0]]: r[s] = g[f'cagr_s|{s}'].median()
            out[(b, o)] = r
        return out
    A = summ(T[T.key == 'P1']); B = summ(T[T.key == 'P2']); REF = ('L', 'none')
    rows = []
    for k in A:
        c1 = A[k]['cr'] > A[REF]['cr'] and B[k]['cr'] > B[REF]['cr']
        subs = sum(A[k][s] > A[REF][s] for s in SUBN['P1']) + sum(B[k][s] > B[REF][s] for s in SUBN['P2'])
        c3 = A[k]['dd'] >= A[REF]['dd'] - 0.05 and B[k]['dd'] >= B[REF]['dd'] - 0.05
        rows.append(dict(base=k[0], over=k[1], d1=A[k]['cr'] - A[REF]['cr'], d2=B[k]['cr'] - B[REF]['cr'], subs=subs, c1=c1, c3=c3,
                         regge=c1 and subs >= 3 and c3, adv=((A[k]['cr'] - A[REF]['cr']) + (B[k]['cr'] - B[REF]['cr'])) / 2,
                         cr1=A[k]['cr'], cr2=B[k]['cr']))
    C = pd.DataFrame(rows).sort_values('adv', ascending=False)
    print(C.round(4).to_string()); C.to_csv(f'{OUT}/criterio_semi_nuovi.csv', index=False)
