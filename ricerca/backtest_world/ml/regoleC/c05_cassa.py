# Prova C (08/11/2026), controllo DICHIARATO DOPO aver visto i risultati principali: la regola "uscita dalla lista" lascia
# molti contanti fermi (1-2 acquisti al mese non bastano a rimpiazzare le uscite). Qui i contanti in attesa sono parcheggiati
# in VWCE (rendimento dell'indice mondiale da un controllo mensile all'altro), per separare l'effetto della regola da quello
# dei contanti. Tutto il resto identico (stessi semi). Nessuna chiamata EODHD.
import os, sys, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import c02_sim as S
import c03_run as R
from multiprocessing import Pool
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)


def job(args):
    key, b, o = args
    D = R.D_of(key); rows = []
    for s in range(R.NSEED):
        r = S.run(D, b, o, s, False, cash_w=True)
        m, _ = R.metrics(key, r, D, False)
        m.update(key=key, base=b, over=o, seed=s); m.pop('ann'); rows.append(m)
    return rows


if __name__ == '__main__':
    jobs = [(k, b, o) for k in ['P1', 'P2', 'P3'] for b, o in S.VARIANTS]
    with Pool(4) as P:
        T = pd.DataFrame([x for rows in P.imap_unordered(job, jobs) for x in rows])
    T.to_pickle(f'{HERE}/dati/runs_cassa_vwce.pkl')
    out = []
    for key, X in T.groupby('key'):
        ref = X[(X.base == 'L') & (X.over == 'none')].set_index('seed')
        for (b, o), g in X.groupby(['base', 'over'], sort=False):
            g = g.set_index('seed')
            out.append(dict(key=key, base=b, over=o, s_med=g.cagr_s.median(), s_dd=g.dd_s.median(), cr_med=g.cagr_cr.median(),
                            cr_dd=g.dd_cr.median(), d_cr=(g.cagr_cr - ref.cagr_cr).median(), gt_ref=(g.cagr_cr > ref.cagr_cr).mean(),
                            cash=g.cash.median(), w=g.cagr_w.iloc[0]))
    O = pd.DataFrame(out)
    O.to_csv(f'{HERE}/dati/cassa_vwce.csv', index=False)
    print(O.round(3).to_string())
