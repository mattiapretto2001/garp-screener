# 2012-26, regola base, dopo le tasse, con costi 0,5% (rapporto) / 0,75% / 1% per operazione
import sys, numpy as np, pandas as pd
sys.path.insert(0, 'regoleC'); import c02_sim as S, c03_run as R
from multiprocessing import Pool
def job(c):
    S.COST = c; D = R.D_of('P2'); out = []
    for s in range(300):
        m, _ = R.metrics('P2', S.run(D, 'L', 'none', s, True), D, True); out.append((m['cagr_s_tax'], m['cagr_c_tax'], m['cagr_w_tax'], m['cagr_c']))
    a = np.array(out); return c, np.median(a, axis=0)
if __name__ == '__main__':
    with Pool(3) as P:
        for c, m in P.imap(job, [0.005, 0.0075, 0.01]):
            print(f'costo {c:.4f}: meta dopo tasse {m[0]:.4f} | 50/50 senza ribil. dopo tasse {m[1]:.4f} | VWCE dopo tasse {m[2]:.4f} | 50/50 senza ribil. prima delle tasse {m[3]:.4f}')
